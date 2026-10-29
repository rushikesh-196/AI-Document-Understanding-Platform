"""
Document Extraction & OCR API Routes
Optimized for high-speed, single-pass pipeline execution, real-time stage monitoring, and activity logging.
"""

import json
import logging
import os
import shutil
import threading
import time
import traceback
import uuid
from flask import Blueprint, current_app, jsonify, request, session
from PIL import Image
import numpy as np

from utils.file_utils import sanitize_file_name, allowed_file
from utils.image_utils import preprocess_image
from utils.language_utils import resolve_ocr_languages, detect_language_from_text
from services.ocr_service import perform_ocr, clean_and_format_raw_text
from services.nlp_service import extract_information
from services.validation_service import validate_extracted_data
from services.document_intelligence import build_document_analysis, build_ai_json_output
from services.layout_reconstruction import reconstruct_document, reconstruct_document_html
from services.pdf_service import extract_pdf_native_text, convert_pdf_to_images
from services.database import save_document_job_record, update_job_stage, log_activity, log_error

from . import api_bp, api_v1_bp

_progress_store = {}
_jobs_lock = threading.Lock()

LOW_CONFIDENCE_THRESHOLD = 70.0


def set_progress(job_id, percent, message, status="processing", result=None, error=None, stage="Processing"):
    with _jobs_lock:
        _progress_store[job_id] = {
            "job_id": job_id,
            "percent": int(percent),
            "message": str(message),
            "status": str(status),
            "stage": str(stage),
            "result": result,
            "error": error,
            "updated_at": time.time(),
        }


def get_progress(job_id):
    with _jobs_lock:
        return _progress_store.get(job_id, {
            "job_id": job_id,
            "percent": 0,
            "message": "Job not found.",
            "status": "not_found",
        })


def init_job(job_id, filename="", user_id=None):
    set_progress(job_id, 5, "Initializing processing pipeline...", status="started", stage="Upload")
    # Save initial pending/processing state
    save_document_job_record({
        "job_id": job_id,
        "user_id": user_id,
        "filename": filename,
        "status": "Processing",
        "current_stage": "Upload"
    })


def complete_job(job_id, result_data):
    set_progress(job_id, 100, "Document processed successfully.", status="completed", stage="Final Result", result=result_data)


def fail_job(job_id, error_message, stage="Processing"):
    set_progress(job_id, 100, error_message, status="failed", stage=stage, error=error_message)


def find_job_record(config, job_id):
    """Locate job JSON data from extracted/outputs directories or memory cache."""
    prog = get_progress(job_id)
    if prog.get("status") == "completed" and prog.get("result"):
        return prog["result"]

    extracted_folder = config.get("EXTRACTED_FOLDER", "extracted")
    output_folder = config.get("OUTPUT_FOLDER", "outputs")

    possible_filenames = [
        f"{job_id}.json",
        f"{job_id}_raw.json",
        f"cache_{job_id}.json",
    ]

    for folder in [extracted_folder, output_folder]:
        if not folder or not os.path.exists(folder):
            continue
        for fname in possible_filenames:
            fp = os.path.join(folder, fname)
            if os.path.exists(fp):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    raw_fp = fp.replace(".json", "_raw.json")
                    if os.path.exists(raw_fp) and raw_fp != fp:
                        try:
                            with open(raw_fp, "r", encoding="utf-8") as rf:
                                raw_data = json.load(rf)
                                data.update(raw_data)
                        except Exception:
                            pass
                    return data
                except Exception as e:
                    logging.error("Failed to read JSON %s: %s", fp, e)

    # Search all json records if direct match fails
    for folder in [extracted_folder, output_folder]:
        if not folder or not os.path.exists(folder):
            continue
        for fn in os.listdir(folder):
            if fn.endswith(".json") and not fn.startswith("cache_"):
                fp = os.path.join(folder, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("job_id") == job_id or data.get("id") == job_id:
                            return data
                except Exception:
                    pass

    return None


def _process_document(app, job_id, saved_file_path, filename, saved_file_name, engine_choice, language, user_id=None):
    """High-speed single-pass worker for OCR + NLP + Summary pipeline with stage tracking."""
    with app.app_context():
        start_time = time.time()
        current_stage = "Upload"
        try:
            current_stage = "File Validation"
            set_progress(job_id, 10, "Validating file format and structure...", stage=current_stage)
            update_job_stage(job_id, current_stage, "Processing")

            ext = saved_file_path.rsplit(".", 1)[-1].lower() if "." in saved_file_path else ""
            file_size_formatted = f"{round(os.path.getsize(saved_file_path) / 1024, 1)} KB" if os.path.exists(saved_file_path) else "0 KB"
            text_pages = []
            confidences = []
            boxes_list = []
            word_confidences = []
            engine_used = "PaddleOCR / WinOCR"
            detected_language = "en"
            language_label = resolve_ocr_languages(language)["label"]
            page_layouts = []

            current_stage = "OCR"
            set_progress(job_id, 25, "Running Optical Character Recognition (OCR)...", stage=current_stage)
            update_job_stage(job_id, current_stage, "Processing")

            if ext == "pdf":
                native_text = extract_pdf_native_text(saved_file_path)
                if native_text and len(native_text.strip()) > 30:
                    raw_text = clean_and_format_raw_text(native_text)
                    confidences.append(99.0)
                    engine_used = "PyMuPDF Direct Extraction"
                    detected_language = detect_language_from_text(native_text)
                    language_label = resolve_ocr_languages(language, detected_lang=detected_language)["label"]
                    page_layouts = [{
                        "page": 1,
                        "text": raw_text,
                        "blocks": [],
                        "boxes": [],
                        "word_boxes": [],
                        "image_width": 800,
                        "image_height": 1000
                    }]
                else:
                    images = convert_pdf_to_images(saved_file_path, dpi=150, max_pages=10)
                    if not images:
                        fail_job(job_id, "No text or pages detected in uploaded PDF.", stage=current_stage)
                        log_error(current_stage, "OCR_NO_PAGES", "No pages rendered from PDF", user_id=user_id, job_id=job_id, document_name=filename)
                        update_job_stage(job_id, current_stage, "Failed", error_msg="No text or pages detected in PDF")
                        return

                    total_pages = len(images)
                    for idx, img in enumerate(images):
                        set_progress(job_id, 25 + int((idx / total_pages) * 20), f"Running OCR on page {idx + 1}/{total_pages}...", stage=current_stage)
                        orig_np = np.array(img)
                        processed_np = preprocess_image(img)

                        ocr_res = perform_ocr(
                            processed_np,
                            original_image_np=orig_np,
                            engine_choice=engine_choice,
                            language=language,
                        )
                        if ocr_res.get("text"):
                            text_pages.append(ocr_res["text"])
                            confidences.append(ocr_res.get("confidence", 90.0))
                            boxes_list.extend(ocr_res.get("boxes", []))
                            word_confidences.extend(ocr_res.get("word_confidences", []))
                            engine_used = ocr_res.get("engine", engine_used)
                            detected_language = ocr_res.get("detected_language", detected_language)
                            language_label = ocr_res.get("language_label", language_label)
                            page_layouts.append({
                                "page": idx + 1,
                                "text": ocr_res.get("text", ""),
                                "blocks": ocr_res.get("blocks", []),
                                "boxes": ocr_res.get("boxes", []),
                                "word_boxes": ocr_res.get("word_boxes", []),
                                "image_width": ocr_res.get("image_width", 800),
                                "image_height": ocr_res.get("image_height", 1000)
                            })

                    raw_text = clean_and_format_raw_text("\n\n".join(text_pages))
            else:
                img = Image.open(saved_file_path).convert("RGB")
                orig_np = np.array(img)
                processed_np = preprocess_image(img)

                ocr_res = perform_ocr(
                    processed_np,
                    original_image_np=orig_np,
                    engine_choice=engine_choice,
                    language=language,
                )
                raw_text = clean_and_format_raw_text(ocr_res.get("text", ""))
                confidences.append(ocr_res.get("confidence", 92.0))
                boxes_list = ocr_res.get("boxes", [])
                word_confidences = ocr_res.get("word_confidences", [])
                engine_used = ocr_res.get("engine", engine_used)
                detected_language = ocr_res.get("detected_language", "en")
                language_label = ocr_res.get("language_label", language_label)
                page_layouts = [{
                    "page": 1,
                    "text": raw_text,
                    "blocks": ocr_res.get("blocks", []),
                    "boxes": boxes_list,
                    "word_boxes": ocr_res.get("word_boxes", []),
                    "image_width": ocr_res.get("image_width", 800),
                    "image_height": ocr_res.get("image_height", 1000)
                }]

            current_stage = "Text Extraction"
            set_progress(job_id, 50, "Formatting and structuring extracted text...", stage=current_stage)
            update_job_stage(job_id, current_stage, "Processing")

            if not raw_text or not raw_text.strip():
                fail_job(job_id, "No readable text detected in document.", stage=current_stage)
                log_error(current_stage, "EMPTY_TEXT_EXTRACTED", "No readable text detected after OCR", user_id=user_id, job_id=job_id, document_name=filename)
                update_job_stage(job_id, current_stage, "Failed", error_msg="No readable text detected in document.")
                return

            avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 90.0
            elapsed_sec = round(time.time() - start_time, 2)

            current_stage = "Document Classification"
            set_progress(job_id, 65, "Classifying document type...", stage=current_stage)
            update_job_stage(job_id, current_stage, "Processing")
            from models.classifier import DocumentClassifier
            doc_type = DocumentClassifier.classify(raw_text)

            current_stage = "Information Extraction"
            set_progress(job_id, 78, "Extracting entities, fields, and tables...", stage=current_stage)
            update_job_stage(job_id, current_stage, "Processing")
            nlp_res = extract_information(raw_text, ocr_confidence=avg_confidence)
            structured_data = nlp_res["structured_data"]
            extracted_fields = nlp_res["extracted_fields_list"]

            intelligence = build_document_analysis(raw_text, filename=filename, confidence_val=avg_confidence)

            # Validation Layer: math verification, format checks, integrity
            validation = validate_extracted_data(
                extracted_fields,
                structured_data=structured_data,
                tables=intelligence.get("tables", []),
                doc_type=doc_type
            )

            low_confidence = avg_confidence < LOW_CONFIDENCE_THRESHOLD
            confidence_warning = "Low OCR confidence. Some information may require manual verification." if low_confidence else None

            formatted_text = reconstruct_document(
                page_layouts=page_layouts,
                raw_text=raw_text,
                bounding_boxes=boxes_list,
            )
            if not formatted_text or not formatted_text.strip():
                formatted_text = raw_text

            formatted_html = reconstruct_document_html(
                page_layouts=page_layouts,
                raw_text=raw_text,
                bounding_boxes=boxes_list,
                structured_data=structured_data,
                tables=intelligence.get("tables", []),
                doc_type=intelligence.get("document_type", doc_type),
            )

            display_formatted_text = formatted_text or raw_text
            display_formatted_html = formatted_html
            structured_layout = formatted_text or raw_text
            unified_entities = intelligence.get("entities", [])

            current_stage = "JSON Generation"
            set_progress(job_id, 90, "Generating clean JSON structure and insights...", stage=current_stage)
            update_job_stage(job_id, current_stage, "Processing")

            ai_json = build_ai_json_output(
                document_type=intelligence.get("document_type", doc_type),
                filename=filename,
                summary=intelligence.get("summary", ""),
                confidence_score=avg_confidence,
                extracted_fields=extracted_fields,
                structured_data=structured_data,
                tables=intelligence.get("tables", []),
                language=detected_language,
                processing_time=f"{elapsed_sec}s",
                entities=nlp_res.get("spacy_entities", []),
                raw_text=raw_text,
            )

            current_stage = "Final Result"
            response_data = {
                "success": True,
                "status": "Completed",
                "ocr_status": "Completed",
                "extraction_status": "Completed",
                "current_stage": "Final Result",
                "job_id": job_id,
                "id": job_id,
                "user_id": user_id,
                "filename": filename,
                "file_type": ext.upper(),
                "file_size": file_size_formatted,
                "saved_file_name": saved_file_name,
                "document_type": intelligence.get("document_type", doc_type),
                "detected_language": detected_language,
                "processing_time": f"{elapsed_sec}s",
                "confidence_score": f"{avg_confidence}%",
                "confidence": avg_confidence,
                "structured_data": structured_data,
                "extracted_fields": extracted_fields,
                "validation": validation,
                "spacy_entities": nlp_res.get("spacy_entities", []),
                "entities": unified_entities,
                "summary": intelligence.get("summary", f"Document classified as {doc_type}."),
                "ai_summary": intelligence.get("summary", ""),
                "raw_text": raw_text,
                "formatted_text": formatted_text,
                "display_formatted_text": display_formatted_text,
                "formatted_html": formatted_html,
                "display_formatted_html": display_formatted_html,
                "structured_layout": structured_layout,
                "tables": intelligence.get("tables", []),
                "grouped_fields": intelligence.get("grouped_fields", []),
                "layout_analysis": intelligence.get("layout_analysis", {}),
                "ai_insights_structured": intelligence.get("ai_insights_structured", {}),
                "engine": engine_used,
            }

            raw_data = {
                "original_filename": filename,
                "overall_ocr_confidence": avg_confidence,
                "low_confidence": low_confidence,
                "confidence_warning": confidence_warning,
                "language_label": language_label,
                "total_extracted_fields": len(extracted_fields),
                "validation": validation,
                "raw_text": raw_text,
                "formatted_text": formatted_text,
                "display_formatted_text": display_formatted_text,
                "formatted_html": formatted_html,
                "display_formatted_html": display_formatted_html,
                "structured_layout": structured_layout,
                "summary_lines": intelligence.get("summary_lines", []),
                "grouped_fields": intelligence.get("grouped_fields", []),
                "layout_analysis": intelligence.get("layout_analysis", {}),
                "tables": intelligence.get("tables", []),
                "entities": intelligence.get("entities", []),
                "bounding_boxes": boxes_list,
                "page_layouts": page_layouts,
                "word_confidences": word_confidences[:500],
                "engine": engine_used,
                "ai_json_output": ai_json,
            }

            # Save to disk
            extracted_folder = app.config["EXTRACTED_FOLDER"]
            output_folder = app.config["OUTPUT_FOLDER"]
            os.makedirs(extracted_folder, exist_ok=True)
            os.makedirs(output_folder, exist_ok=True)

            record_file = f"{job_id}.json"
            raw_file = f"{job_id}_raw.json"

            for folder in [extracted_folder, output_folder]:
                with open(os.path.join(folder, record_file), "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=2, ensure_ascii=False)
                with open(os.path.join(folder, raw_file), "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, indent=2, ensure_ascii=False)

            # Persist to database
            save_document_job_record(response_data)
            log_activity(
                "Document processing completed",
                user_id=user_id,
                details=f"Document: {filename}, Type: {doc_type}, Confidence: {avg_confidence}%, Time: {elapsed_sec}s"
            )

            combined_data = {**response_data, **raw_data}
            complete_job(job_id, combined_data)

        except Exception as e:
            st = traceback.format_exc()
            logging.exception("OCR extraction worker error for job %s at stage %s", job_id, current_stage)
            error_msg = f"Processing failed at stage '{current_stage}': {str(e)}"
            fail_job(job_id, error_msg, stage=current_stage)
            log_error(current_stage, "WORKER_EXCEPTION", str(e), user_id=user_id, job_id=job_id, document_name=filename, stack_trace=st)
            update_job_stage(job_id, current_stage, "Failed", error_msg=str(e))
            log_activity("Document processing failed", user_id=user_id, details=f"File: {filename}, Stage: {current_stage}, Error: {str(e)}")


@api_bp.route("/progress/<job_id>", methods=["GET"])
@api_v1_bp.route("/progress/<job_id>", methods=["GET"])
def get_job_progress(job_id):
    progress = get_progress(job_id)
    if progress.get("status") == "completed" and progress.get("result"):
        progress = {**progress, "job_id": job_id}
    return jsonify(progress), 200


@api_bp.route("/result/<job_id>", methods=["GET"])
@api_v1_bp.route("/result/<job_id>", methods=["GET"])
@api_bp.route("/results/<job_id>", methods=["GET"])
@api_v1_bp.route("/results/<job_id>", methods=["GET"])
def get_job_result_api(job_id):
    """Standardized Result API returning structured JSON."""
    job_data = find_job_record(current_app.config, job_id)
    if job_data:
        return jsonify({
            "success": True,
            "job_id": job_id,
            "status": "completed",
            "document": {
                "filename": job_data.get("filename", "Document"),
                "document_type": job_data.get("document_type", "General Document")
            },
            "extracted_data": job_data.get("structured_data", {}),
            "important_values": job_data.get("spacy_entities", []),
            "key_findings": job_data.get("extracted_fields", []),
            "ai_summary": job_data.get("summary", ""),
            "raw_text": job_data.get("raw_text", ""),
            "formatted_text": job_data.get("formatted_text", ""),
            "raw_json": job_data
        }), 200

    progress = get_progress(job_id)
    if progress.get("status") in ["processing", "started", "queued"]:
        return jsonify({
            "success": True,
            "job_id": job_id,
            "status": "processing",
            "percent": progress.get("percent", 15),
            "message": progress.get("message", "Processing document...")
        }), 200

    return jsonify({
        "success": False,
        "job_id": job_id,
        "status": "not_found",
        "message": f"No result found for Job ID: {job_id}"
    }), 404


@api_bp.route("/search", methods=["GET"])
@api_v1_bp.route("/search", methods=["GET"])
def search_documents():
    query = request.args.get("q", "").strip().lower()
    results = []
    seen_ids = set()
    for folder in [current_app.config["EXTRACTED_FOLDER"], current_app.config["OUTPUT_FOLDER"]]:
        if os.path.exists(folder):
            for fn in os.listdir(folder):
                if not fn.endswith('.json') or fn.startswith('cache_') or fn.endswith('_raw.json'):
                    continue
                try:
                    with open(os.path.join(folder, fn), 'r', encoding='utf-8') as handle:
                        data = json.load(handle)
                    jid = data.get("job_id", data.get("id", fn))
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)

                    text = f"{data.get('filename', '')} {data.get('document_type', '')} {data.get('summary', '')} {json.dumps(data.get('structured_data', {}))}".lower()
                    if not query or query in text:
                        results.append(data)
                except Exception:
                    continue
    return jsonify({"success": True, "count": len(results), "results": results[:30]})


@api_bp.route("/sample/<doc_type>", methods=["POST"])
@api_v1_bp.route("/sample/<doc_type>", methods=["POST"])
def process_sample_document(doc_type):
    """Process a pre-bundled sample document for demo/portfolio purposes."""
    samples = {
        "invoice": "sample_invoice.png",
        "receipt": "sample_receipt.png",
        "medical": "sample_medical.png",
    }
    sample_file = samples.get(doc_type)
    if not sample_file:
        return jsonify({"success": False, "message": "Unknown sample type. Use: invoice, receipt, or medical."}), 400

    sample_path = os.path.join(current_app.static_folder, "samples", sample_file)
    if not os.path.exists(sample_path):
        return jsonify({"success": False, "message": "Sample file not found on server."}), 404

    job_id = f"SAMPLE-{uuid.uuid4().hex[:8].upper()}"
    raw_uid = session.get("user_id") or request.form.get("user_id") or (request.get_json(silent=True) or {}).get("user_id") or request.headers.get("X-User-Id")
    user_id = None
    if raw_uid:
        try:
            user_id = int(raw_uid)
        except (ValueError, TypeError):
            user_id = None
    filename = sample_file
    saved_file_name = f"{job_id}_{sample_file}"

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    saved_file_path = os.path.join(upload_folder, saved_file_name)
    shutil.copy2(sample_path, saved_file_path)

    init_job(job_id, filename=filename, user_id=user_id)
    log_activity("Sample document loaded", user_id=user_id, details=f"Sample: {doc_type}")

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_process_document,
        args=(app, job_id, saved_file_path, filename, saved_file_name, "auto", "en", user_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "status": "processing",
        "job_id": job_id,
        "message": f"Sample '{doc_type}' loaded. Poll /api/v1/progress/{job_id} for updates.",
    }), 202


@api_bp.route("/extract", methods=["POST"])
@api_v1_bp.route("/extract", methods=["POST"])
@api_bp.route("/process", methods=["POST"])
@api_v1_bp.route("/process", methods=["POST"])
def extract_document():
    engine_choice = request.form.get("engine", "auto")
    language = request.form.get("language", "en")
    raw_uid = session.get("user_id") or request.form.get("user_id") or (request.get_json(silent=True) or {}).get("user_id") or request.headers.get("X-User-Id")
    user_id = None
    if raw_uid:
        try:
            user_id = int(raw_uid)
        except (ValueError, TypeError):
            user_id = None
    saved_file_path = None
    filename = None
    saved_file_name = None
    job_id = None

    if "file" in request.files and request.files["file"].filename != "":
        file = request.files["file"]
        if not allowed_file(file.filename):
            return jsonify({
                "success": False,
                "message": "Unsupported file type. Please upload PNG, JPG, JPEG, TIFF, or PDF.",
            }), 400

        clean_filename = sanitize_file_name(file.filename)
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        filename = clean_filename
        saved_file_name = f"{job_id}_{clean_filename}"

        upload_folder = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)
        saved_file_path = os.path.join(upload_folder, saved_file_name)
        file.save(saved_file_path)

    elif "filename" in request.form:
        filename = request.form.get("filename")
        saved_file_name = filename
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        saved_file_path = os.path.join(upload_folder, filename)
        if not os.path.exists(saved_file_path):
            return jsonify({"success": False, "message": "File not found on server."}), 404
        job_id = filename.split("_", 1)[0] if "_" in filename else f"JOB-{uuid.uuid4().hex[:8].upper()}"

    else:
        return jsonify({"success": False, "message": "No document file provided."}), 400

    init_job(job_id, filename=filename, user_id=user_id)
    log_activity("User uploaded document", user_id=user_id, details=f"File: {filename}, Job ID: {job_id}")

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_process_document,
        args=(app, job_id, saved_file_path, filename, saved_file_name, engine_choice, language, user_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "status": "processing",
        "job_id": job_id,
        "message": "Extraction started. Poll /api/v1/progress/{job_id} for updates.",
    }), 202
