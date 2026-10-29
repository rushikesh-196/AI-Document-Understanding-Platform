# Frontend - AI Document Understanding Platform

React frontend with modern glassmorphism UI for document AI platform.

## Tech Stack

- **Framework**: React 18.2.0 with TypeScript
- **Build Tool**: Vite 5.0.11
- **Styling**: Tailwind CSS 3.4.1
- **Animations**: Framer Motion 10.18.0
- **Routing**: React Router DOM 6.21.0
- **HTTP Client**: Axios 1.6.5
- **File Upload**: React Dropzone 14.2.3
- **Charts**: Recharts 2.10.4
- **Icons**: Lucide React 0.303.0

## Installation

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

4. Preview production build:
```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Dashboard/          # Dashboard components
│   │   ├── Upload/             # Upload components
│   │   ├── Classification/     # Classification UI
│   │   ├── LayoutAnalysis/     # Layout visualization
│   │   ├── OCR/                # OCR display
│   │   ├── Extraction/         # Extraction UI
│   │   ├── NER/                # Entity visualization
│   │   ├── Summary/            # Summary display
│   │   ├── Confidence/         # Confidence scores
│   │   ├── Export/             # Export functionality
│   │   ├── Search/             # Search components
│   │   ├── History/            # History timeline
│   │   └── Shared/
│   │       └── Layout.tsx      # Main layout component
│   ├── pages/
│   │   ├── Dashboard.tsx       # Dashboard page
│   │   ├── Upload.tsx          # Upload page
│   │   ├── DocumentView.tsx    # Document details page
│   │   └── History.tsx         # History page
│   ├── services/
│   │   └── api.ts              # API client
│   ├── types/
│   │   └── index.ts            # TypeScript types
│   ├── context/
│   │   └── ThemeContext.tsx    # Theme management
│   ├── utils/
│   │   └── cn.ts               # Utility functions
│   ├── App.tsx                 # Root component
│   ├── main.tsx                # Entry point
│   └── index.css               # Global styles
├── public/                     # Static assets
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Features

### Dashboard
- Real-time statistics
- Document type distribution charts
- Performance metrics
- Recent uploads list
- Animated confidence indicators

### Upload
- Drag & drop file upload
- File type validation
- Upload progress tracking
- Multiple file format support (PDF, JPG, PNG, TIFF)
- 16MB file size limit

### Document View
- Tabbed interface for different views
- Overview with AI summary
- OCR text display with copy functionality
- Layout analysis visualization
- Named entity color-coding
- Extracted information display
- Export options (JSON, CSV, TXT)
- Animated confidence score gauges

### History
- Document list with search
- Filter by type and status
- Delete functionality
- Processing statistics
- Date and duration tracking

### UI/UX
- Glassmorphism design
- Dark/Light mode toggle
- Smooth animations
- Responsive layout
- Loading skeletons
- Toast notifications
- Professional typography

## API Integration

The frontend communicates with the backend via the API client in `src/services/api.ts`:

```typescript
import { documentApi } from '../services/api';

// Upload document
const result = await documentApi.uploadDocument(file);

// Get documents
const documents = await documentApi.getDocuments();

// Get document details
const document = await documentApi.getDocument(id);

// Export document
const data = await documentApi.exportJSON(documentId);
```

## Theme Management

The application uses React Context for theme management:

```typescript
import { useTheme } from '../context/ThemeContext';

const { isDark, toggleTheme } = useTheme();
```

## Styling

### Custom CSS Classes

Defined in `src/index.css`:
- `.glass-card` - Glassmorphism card style
- `.glass-input` - Glassmorphism input style
- `.glass-button` - Primary button style
- `.glass-button-secondary` - Secondary button style
- `.sidebar-item` - Sidebar navigation items
- `.stat-card` - Dashboard stat cards
- `.upload-zone` - Upload drop zone
- `.confidence-bar` - Confidence score bars
- `.entity-tag` - Entity display tags
- `.loading-skeleton` - Loading skeleton animation

### Tailwind Configuration

Extended in `tailwind.config.js`:
- Custom colors (primary palette, glass colors)
- Custom animations (fade-in, slide-up, scale-in, pulse-slow)
- Extended backdrop blur options

## Component Patterns

### Loading States
```typescript
const [loading, setLoading] = useState(true);

if (loading) {
  return <div className="h-32 loading-skeleton" />;
}
```

### Error Handling
```typescript
try {
  const data = await documentApi.getDocument(id);
  setDocument(data);
} catch (error) {
  console.error('Failed to load document:', error);
} finally {
  setLoading(false);
}
```

### Motion Animations
```typescript
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
>
  {/* Content */}
</motion.div>
```

## Responsive Design

The application uses Tailwind's responsive utilities:
- Mobile-first approach
- Breakpoints: sm, md, lg, xl
- Grid and flex layouts
- Responsive typography

## Build Configuration

### Vite Config
- API proxy to backend
- React plugin
- Development server on port 3000

### TypeScript Config
- Strict mode enabled
- Path aliases support
- React JSX transform

## Deployment

### Build for Production
```bash
npm run build
```

### Deploy to Static Hosting
The `dist/` folder can be deployed to:
- Vercel
- Netlify
- AWS S3 + CloudFront
- GitHub Pages
- Any static hosting service

### Environment Variables
Create `.env` file:
```
VITE_API_URL=http://your-backend-url.com
```

## Performance

- Code splitting via React Router
- Lazy loading for large components
- Optimized images
- Bundle size optimization
- Fast initial load

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Development Tips

1. **Hot Module Replacement**: Vite provides instant HMR
2. **Type Safety**: TypeScript catches errors at build time
3. **Component Organization**: Keep components small and focused
4. **API Calls**: Use the centralized API client
5. **State Management**: Use React hooks for local state
6. **Styling**: Prefer Tailwind utilities over custom CSS

## Troubleshooting

### Port Already in Use
Change port in `vite.config.ts`:
```typescript
server: {
  port: 3001, // Change port
}
```

### API Connection Issues
Check:
1. Backend is running
2. API proxy configuration in `vite.config.ts`
3. CORS settings on backend

### Build Errors
1. Clear node_modules and reinstall
2. Check TypeScript types
3. Verify all imports are correct
