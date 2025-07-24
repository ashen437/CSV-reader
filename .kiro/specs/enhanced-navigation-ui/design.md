# Design Document

## Overview

This design transforms the CSV Reader application from a single-page interface into a multi-page application with enhanced navigation, improved AI grouping configuration, and a dedicated Charts page with ChatGPT-like document interaction. The design maintains the existing functionality while adding new navigation patterns and user experience improvements.

## Architecture

### Current State Analysis
- **Frontend**: React 18.2.0 with React Router DOM 6.3.0
- **Styling**: Tailwind CSS 3.1.0
- **Current Structure**: Single-page app with conditional rendering
- **Existing Routes**: `/`, `/configure-groups/:fileId`, `/group-management/:fileId`
- **Logo Location**: `frontend/public/assets/logo.jpg`

### Proposed Architecture Changes
- **Navigation System**: Global navigation bar component
- **Page Structure**: Home page (current functionality) + new Charts page
- **State Management**: Shared document state across pages
- **Routing**: Enhanced routing with navigation integration

## Components and Interfaces

### 1. Navigation Bar Component (`NavigationBar.js`)

```javascript
// Component Interface
interface NavigationBarProps {
  currentPage: 'home' | 'charts';
}

// Key Features
- Logo display from frontend/public/assets/logo.jpg
- Navigation menu items (Home, Charts)
- Active page highlighting
- Responsive design for mobile/desktop
- Consistent styling with existing Tailwind theme
```

**Design Specifications:**
- **Height**: 64px (h-16)
- **Background**: White with shadow-sm border-b
- **Logo**: 40px height, positioned left
- **Menu Items**: Horizontal layout on desktop, hamburger menu on mobile
- **Active State**: Blue accent color matching existing theme
- **Responsive Breakpoint**: Mobile-first approach with lg: breakpoint

### 2. Enhanced Home Page (`App.js` modifications)

**Changes Required:**
- Replace "Analyze with AI" button with "Configure AI Groups"
- Integrate NavigationBar component
- Maintain all existing functionality
- Update button styling and labeling

**Button Specifications:**
- **Text**: "Configure AI Groups" 
- **Icon**: Settings/configuration icon (existing cog icon)
- **Styling**: Purple theme (bg-purple-600) to differentiate from analysis actions
- **Functionality**: Navigate to `/configure-groups/:fileId`

### 3. Charts Page Component (`ChartsPage.js`)

```javascript
// Component Interface
interface ChartsPageProps {}

// Layout Structure
- Two-panel layout (sidebar + main content)
- Document list sidebar (left, 300px width)
- Chat interface main area (right, remaining width)
- Responsive: Single column on mobile with collapsible sidebar
```

**Layout Specifications:**
- **Desktop Layout**: `grid-cols-[300px_1fr]`
- **Mobile Layout**: Single column with overlay sidebar
- **Sidebar Width**: 300px fixed on desktop
- **Breakpoint**: lg: for desktop layout
- **Height**: Full viewport height minus navigation bar

### 4. Document List Sidebar (`DocumentSidebar.js`)

```javascript
// Component Interface
interface DocumentSidebarProps {
  documents: Document[];
  selectedDocument: Document | null;
  onDocumentSelect: (document: Document) => void;
  isMobileOpen: boolean;
  onMobileClose: () => void;
}

// Document Interface
interface Document {
  file_id: string;
  filename: string;
  upload_date: string;
  total_rows: number;
  status: 'uploaded' | 'processing' | 'completed' | 'error';
  has_charts: boolean;
}
```

**Design Specifications:**
- **Background**: White with border-r
- **Item Height**: 80px per document
- **Selected State**: Blue background (bg-blue-50) with left border accent
- **Hover State**: Light gray background (hover:bg-gray-50)
- **Document Info Display**:
  - Filename (truncated if long)
  - Upload date (relative format: "2 hours ago")
  - Row count ("1,234 rows")
  - Status badge
  - Chart indicator icon if has_charts is true

### 5. Chat Interface Component (`ChatInterface.js`)

```javascript
// Component Interface
interface ChatInterfaceProps {
  selectedDocument: Document | null;
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  isLoading: boolean;
}

// ChatMessage Interface
interface ChatMessage {
  id: string;
  message: string;
  sender: 'user' | 'ai';
  timestamp: string;
  chart_data?: string;
  chart_type?: string;
}
```

**Design Specifications:**
- **Layout**: Full height with header, messages area, and input
- **Header**: Document name and status (60px height)
- **Messages Area**: Scrollable with auto-scroll to bottom
- **Message Styling**: 
  - User messages: Right-aligned, blue background
  - AI messages: Left-aligned, gray background
  - Chart display: Inline image rendering
- **Input Area**: Fixed bottom with send button
- **Empty State**: Centered prompt to select document

### 6. Shared State Management

**Document Context (`DocumentContext.js`)**:
```javascript
// Context Interface
interface DocumentContextValue {
  documents: Document[];
  selectedDocument: Document | null;
  chatHistories: Record<string, ChatMessage[]>;
  selectDocument: (document: Document) => void;
  refreshDocuments: () => void;
  addChatMessage: (fileId: string, message: ChatMessage) => void;
}
```

## Data Models

### Enhanced Document Model
```javascript
interface Document {
  file_id: string;
  filename: string;
  upload_date: string; // ISO string
  total_rows: number;
  columns: string[];
  status: 'uploaded' | 'processing' | 'completed' | 'error';
  has_charts: boolean; // New field to indicate chart availability
  last_chat_activity?: string; // ISO string for last chat interaction
}
```

### Chat Message Model
```javascript
interface ChatMessage {
  id: string; // UUID
  file_id: string;
  message: string;
  sender: 'user' | 'ai';
  timestamp: string; // ISO string
  chart_data?: string; // Base64 or URL
  chart_type?: 'image_url' | 'base64';
}
```

## Error Handling

### Navigation Errors
- **Route Not Found**: Display 404 page with navigation back to Home
- **Invalid Document ID**: Redirect to Charts page with error message
- **Logo Loading Failure**: Fallback to text-based logo

### Document Loading Errors
- **API Failures**: Show error state in document list
- **Empty Document List**: Display empty state with upload prompt
- **Document Selection Errors**: Clear selection and show error message

### Chat Interface Errors
- **Message Send Failures**: Show retry option and error indicator
- **Chart Loading Failures**: Display error message in chat
- **Connection Issues**: Show offline indicator and queue messages

## Testing Strategy

### Unit Testing
- **NavigationBar Component**: Active state, responsive behavior, logo display
- **DocumentSidebar Component**: Document selection, filtering, responsive layout
- **ChatInterface Component**: Message sending, chart display, scroll behavior
- **DocumentContext**: State management, API integration, error handling

### Integration Testing
- **Navigation Flow**: Home to Charts page navigation
- **Document Selection**: Cross-component state synchronization
- **Chat Functionality**: End-to-end message flow with backend
- **Responsive Design**: Layout behavior across breakpoints

### User Experience Testing
- **Navigation Usability**: Menu accessibility and visual feedback
- **Document Management**: Selection and switching between documents
- **Chat Experience**: Message flow and chart interaction
- **Mobile Experience**: Touch interactions and responsive layout

## Implementation Considerations

### Performance Optimizations
- **Document List**: Virtual scrolling for large document lists
- **Chat Messages**: Message pagination for long conversations
- **Chart Rendering**: Lazy loading and caching for chart images
- **State Management**: Memoization for expensive computations

### Accessibility Features
- **Navigation**: Keyboard navigation and ARIA labels
- **Document List**: Screen reader support and focus management
- **Chat Interface**: Message announcements and input labeling
- **Color Contrast**: WCAG AA compliance for all UI elements

### Mobile Responsiveness
- **Navigation**: Hamburger menu with slide-out drawer
- **Document Sidebar**: Overlay modal on mobile devices
- **Chat Interface**: Optimized input area and message display
- **Touch Interactions**: Appropriate touch targets and gestures

### Browser Compatibility
- **Modern Browsers**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Fallbacks**: Graceful degradation for older browsers
- **Progressive Enhancement**: Core functionality without JavaScript

## Migration Strategy

### Phase 1: Navigation Infrastructure
1. Create NavigationBar component
2. Update routing structure
3. Integrate navigation into existing pages
4. Replace "Analyze with AI" button

### Phase 2: Charts Page Foundation
1. Create ChartsPage component structure
2. Implement DocumentSidebar component
3. Set up basic layout and routing
4. Add document loading functionality

### Phase 3: Chat Integration
1. Implement ChatInterface component
2. Integrate with existing chat API endpoints
3. Add message history management
4. Implement chart display functionality

### Phase 4: Polish and Optimization
1. Add responsive design refinements
2. Implement error handling
3. Add loading states and animations
4. Conduct user testing and refinements