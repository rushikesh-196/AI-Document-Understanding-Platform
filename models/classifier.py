"""
Automated Document Classifier — Enhanced for 16 Document Categories
"""

import re


class DocumentClassifier:
    """
    Intelligent heuristic & pattern-matching Document Classifier.
    Supports:
      1. Invoice
      2. Receipt
      3. Resume / CV
      4. Medical Report
      5. Bank Statement
      6. Aadhaar Card
      7. PAN Card
      8. Passport
      9. Driving License
      10. Business Card
      11. Purchase Order
      12. Utility Bill
      13. Certificate
      14. Restaurant Bill
      15. Legal Contract / Form
      16. General Document
    """

    DOCUMENT_PATTERNS = {
        "Invoice": [
            (r"\binvoice\b", 3), (r"\btax invoice\b", 4), (r"\bbill to\b", 3), (r"\bdue date\b", 2),
            (r"\binvoice number\b", 4), (r"\binvoice no\b", 3), (r"\binv #\b", 3), (r"\bgstin\b", 3),
            (r"\bunit price\b", 2), (r"\bsubtotal\b", 2), (r"\btaxable value\b", 3), (r"\bpo number\b", 2),
            (r"\bpayment terms\b", 2), (r"\bship to\b", 2), (r"\bgrand total\b", 2), (r"\bhsn\b", 2)
        ],
        "Receipt": [
            (r"\breceipt\b", 3), (r"\bcash receipt\b", 4), (r"\bcashier\b", 2), (r"\bthank you for shopping\b", 3),
            (r"\bmerchant\b", 2), (r"\btotal paid\b", 3), (r"\bpayment mode\b", 2), (r"\btransaction id\b", 3),
            (r"\bcard ending\b", 2), (r"\bchange due\b", 3), (r"\bpaid by\b", 2), (r"\bitem count\b", 2)
        ],
        "Medical Report": [
            (r"\bmedical report\b", 4), (r"\bpatient name\b", 4), (r"\bpatient id\b", 4), (r"\bdoctor\b", 2),
            (r"\bhospital\b", 3), (r"\bclinic\b", 3), (r"\bdiagnosis\b", 4), (r"\bprescription\b", 4),
            (r"\blab report\b", 4), (r"\bclinical\b", 2), (r"\bsurgeon\b", 3), (r"\bhemoglobin\b", 3),
            (r"\bblood pressure\b", 3), (r"\btreatment\b", 2), (r"\bmedication\b", 3), (r"\bconsultant\b", 2)
        ],
        "Resume / CV": [
            (r"\bcurriculum vitae\b", 5), (r"\bresume\b", 4), (r"\bwork experience\b", 4), (r"\beducation\b", 3),
            (r"\bskills\b", 2), (r"\bprofessional summary\b", 3), (r"\bcareer objective\b", 3), (r"\bprojects\b", 2),
            (r"\bqualifications\b", 2), (r"\bbachelor\b", 2), (r"\bmaster\b", 2), (r"\buniversity\b", 2),
            (r"\btechnical skills\b", 3), (r"\bcertifications\b", 2), (r"\blinkedin\.com\b", 3), (r"\bgithub\.com\b", 3)
        ],
        "Bank Statement": [
            (r"\bbank statement\b", 5), (r"\baccount statement\b", 4), (r"\baccount number\b", 3),
            (r"\bopening balance\b", 4), (r"\bclosing balance\b", 4), (r"\bdebit\b", 2), (r"\bcredit\b", 2),
            (r"\bifsc code\b", 4), (r"\bifsc\b", 3), (r"\bbranch\b", 2), (r"\bstatement period\b", 3),
            (r"\bavailable balance\b", 3), (r"\bwithdrawal\b", 2), (r"\bdeposit\b", 2), (r"\btransaction date\b", 2)
        ],
        "Aadhaar Card": [
            (r"\baadhaar\b", 5), (r"\buidai\b", 5), (r"\bgovernment of india\b", 3),
            (r"\bunique identification authority\b", 5), (r"\bmera aadhaar\b", 5), (r"\benrolment no\b", 4),
            (r"\byob\b", 3), (r"\bmale\b|\bfemale\b", 1)
        ],
        "PAN Card": [
            (r"\bincome tax department\b", 5), (r"\bpermanent account number\b", 5), (r"\bpan card\b", 5),
            (r"\bgovernment of india\b", 3), (r"\bfather's name\b", 3), (r"\bpan\b", 2)
        ],
        "Passport": [
            (r"\bpassport\b", 5), (r"\bpassport no\b", 4), (r"\brepublic of india\b|\bunited states of america\b", 4),
            (r"\bnationality\b", 3), (r"\bplace of birth\b", 3), (r"\bdate of expiry\b", 3),
            (r"\bdate of issue\b", 2), (r"\bmachine readable\b", 3), (r"\bsurname\b", 2)
        ],
        "Driving License": [
            (r"\bdriving licen[sc]e\b", 5), (r"\bdl no\b", 4), (r"\bauthori[sz]ed to drive\b", 4),
            (r"\blicensing authority\b", 3), (r"\brto\b", 2), (r"\btransport\b|\bnon-transport\b", 2),
            (r"\bvalid till\b", 2), (r"\bvehicle class\b", 3)
        ],
        "Purchase Order": [
            (r"\bpurchase order\b", 5), (r"\bpo number\b", 4), (r"\bpo date\b", 3), (r"\bvendor code\b", 3),
            (r"\border date\b", 2), (r"\bshipping terms\b", 2), (r"\brequisition\b", 3)
        ],
        "Utility Bill": [
            (r"\belectricity bill\b", 5), (r"\bwater bill\b", 5), (r"\bgas bill\b", 5), (r"\bpower corporation\b", 4),
            (r"\bconsumer number\b", 4), (r"\bconnection id\b", 4), (r"\bbilling cycle\b", 3), (r"\bmeter number\b", 4),
            (r"\bunits consumed\b", 4), (r"\btariff\b", 2)
        ],
        "Business Card": [
            (r"\bceo\b|\bcto\b|\bcfo\b|\bcoo\b|\bvp\b", 2), (r"\bmanaging director\b", 3), (r"\bfounder\b", 2),
            (r"\bmobile:\b|\btel:\b|\bcell:\b", 2), (r"\bemail:\b|\bwebsite:\b", 2), (r"\bconsultant\b", 2)
        ],
        "Restaurant Bill": [
            (r"\brestaurant\b", 4), (r"\bcafe\b|\bbistro\b|\bdiner\b", 3), (r"\btable no\b", 4),
            (r"\bwaiter\b|\bserver\b", 3), (r"\bfood\b|\bbeverage\b", 2), (r"\bguest check\b", 4),
            (r"\bservice charge\b", 3), (r"\btip\b", 2), (r"\bcovers\b", 2)
        ],
        "Certificate": [
            (r"\bcertificate\b", 4), (r"\bhereby certif(?:y|ies)\b", 5), (r"\bawarded to\b", 4),
            (r"\bsuccessful completion\b", 4), (r"\bin recognition of\b", 4), (r"\bhas completed\b", 3)
        ],
        "Legal Contract / Form": [
            (r"\bagreement\b|\bcontract\b", 3), (r"\bterms and conditions\b", 3), (r"\bparty of the first part\b", 4),
            (r"\bwitnesseth\b", 4), (r"\bherein\b|\bthereof\b", 2), (r"\bapplication form\b", 4)
        ]
    }

    @classmethod
    def classify(cls, text):
        if not text or not str(text).strip():
            return "General Document"

        text_lower = text.lower()
        scores = {doc_type: 0 for doc_type in cls.DOCUMENT_PATTERNS}

        for doc_type, patterns in cls.DOCUMENT_PATTERNS.items():
            for pattern, weight in patterns:
                matches = re.findall(pattern, text_lower)
                scores[doc_type] += len(matches) * weight

        # Get highest matching type
        max_type = max(scores, key=scores.get)
        if scores[max_type] > 0:
            return max_type

        return "General Document"
