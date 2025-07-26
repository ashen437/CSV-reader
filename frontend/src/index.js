import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import "./index.css";
import App from "./App";
import GroupManagement from "./components/GroupManagement";
import GroupConfigurationPreview from "./components/GroupConfigurationPreview";
import Groups from "./components/Groups";
import EditGroups from "./components/EditGroups";
import NavigationBar from "./components/NavigationBar";
import NavigationErrorBoundary from "./components/NavigationErrorBoundary";
import { DocumentProvider } from "./contexts/DocumentContext";
import { ColumnSelectionProvider } from "./contexts/ColumnSelectionContext";
import ErrorBoundary from "./components/ErrorBoundary";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <DocumentProvider>
        <ColumnSelectionProvider>
          <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <NavigationErrorBoundary>
              <NavigationBar />
            </NavigationErrorBoundary>
            <Routes>
              <Route path="/" element={<App />} />
              <Route path="/groups" element={<Groups />} />
              <Route path="/edit-groups/:groupId" element={<EditGroups />} />
              <Route path="/configure-groups/:fileId" element={<GroupConfigurationPreview />} />
              <Route path="/group-management/:fileId" element={<GroupManagement />} />
              <Route path="*" element={
                <div style={{ padding: '20px', textAlign: 'center' }}>
                  <h2>Page Not Found</h2>
                  <p>The page you're looking for doesn't exist.</p>
                  <button onClick={() => window.location.href = '/'}>
                    Go back to home
                  </button>
                </div>
              } />
            </Routes>
          </Router>
        </ColumnSelectionProvider>
      </DocumentProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
