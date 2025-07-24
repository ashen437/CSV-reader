import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DocumentProvider, useDocumentContext } from '../DocumentContext';

// Mock fetch
global.fetch = jest.fn();

// Test component to access context
const TestComponent = () => {
  const {
    documents,
    selectedDocument,
    chatHistories,
    isLoading,
    error,
    connectionStatus,
    retryCount,
    selectDocument,
    refreshDocuments,
    addChatMessage,
    getChatMessages,
    clearChatHistory
  } = useDocumentContext();

  return (
    <div>
      <div data-testid="documents-count">{documents.length}</div>
      <div data-testid="selected-document">{selectedDocument?.filename || 'none'}</div>
      <div data-testid="loading">{isLoading.toString()}</div>
      <div data-testid="error">{error || 'none'}</div>
      <div data-testid="connection-status">{connectionStatus}</div>
      <div data-testid="retry-count">{retryCount}</div>
      <div data-testid="chat-messages">{getChatMessages('1').length}</div>
      
      <button onClick={() => refreshDocuments()} data-testid="refresh-btn">
        Refresh
      </button>
      <button 
        onClick={() => selectDocument({ file_id: '1', filename: 'test.csv' })} 
        data-testid="select-btn"
      >
        Select
      </button>
      <button 
        onClick={() => addChatMessage('1', { 
          message: 'test', 
          sender: 'user', 
          timestamp: new Date().toISOString() 
        })} 
        data-testid="add-message-btn"
      >
        Add Message
      </button>
      <button 
        onClick={() => clearChatHistory('1')} 
        data-testid="clear-history-btn"
      >
        Clear History
      </button>
    </div>
  );
};

const mockDocuments = [
  {
    file_id: '1',
    filename: 'sales_data.csv',
    upload_date: '2024-01-15T10:30:00Z',
    total_rows: 1500,
    columns: ['date', 'product', 'price'],
    status: 'completed',
    has_charts: false
  },
  {
    file_id: '2',
    filename: 'customer_data.csv',
    upload_date: '2024-01-14T09:15:00Z',
    total_rows: 850,
    columns: ['id', 'name', 'email'],
    status: 'processing',
    has_charts: true
  }
];

const mockChatHistory = {
  messages: [
    {
      id: '1',
      message: 'Hello',
      sender: 'user',
      timestamp: '2024-01-15T10:30:00Z'
    },
    {
      id: '2',
      message: 'Hi there!',
      sender: 'ai',
      timestamp: '2024-01-15T10:31:00Z'
    }
  ]
};

describe('DocumentContext', () => {
  beforeEach(() => {
    fetch.mockClear();
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('Context Provider', () => {
    test('throws error when used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      
      expect(() => {
        render(<TestComponent />);
      }).toThrow('useDocumentContext must be used within a DocumentProvider');
      
      consoleSpy.mockRestore();
    });

    test('provides initial context values', () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDocuments
      });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      expect(screen.getByTestId('documents-count')).toHaveTextContent('0');
      expect(screen.getByTestId('selected-document')).toHaveTextContent('none');
      expect(screen.getByTestId('loading')).toHaveTextContent('true');
      expect(screen.getByTestId('error')).toHaveTextContent('none');
      expect(screen.getByTestId('connection-status')).toHaveTextContent('connected');
      expect(screen.getByTestId('retry-count')).toHaveTextContent('0');
    });
  });

  describe('Document Loading', () => {
    test('loads documents on mount', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDocuments
      });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/files', expect.any(Object));
    });

    test('handles document loading errors', async () => {
      fetch.mockRejectedValueOnce(new Error('Network error'));

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Network error');
        expect(screen.getByTestId('connection-status')).toHaveTextContent('disconnected');
        expect(screen.getByTestId('loading')).toHaveTextContent('false');
      });
    });

    test('handles API errors with retry logic', async () => {
      fetch
        .mockRejectedValueOnce(new Error('Server error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      // First call fails
      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Server error');
      });

      // Trigger retry
      act(() => {
        screen.getByTestId('refresh-btn').click();
      });

      // Second call succeeds
      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
        expect(screen.getByTestId('error')).toHaveTextContent('none');
      });
    });

    test('handles timeout errors', async () => {
      fetch.mockImplementationOnce(() => new Promise(() => {})); // Never resolves

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      // Fast-forward time to trigger timeout
      act(() => {
        jest.advanceTimersByTime(10000);
      });

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Request timed out. Please check your connection.');
        expect(screen.getByTestId('connection-status')).toHaveTextContent('disconnected');
      });
    });
  });

  describe('Document Selection', () => {
    test('selects document and loads chat history', async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockChatHistory
        });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
      });

      act(() => {
        screen.getByTestId('select-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('selected-document')).toHaveTextContent('test.csv');
        expect(screen.getByTestId('chat-messages')).toHaveTextContent('2');
      });

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/chat-history/1');
    });

    test('handles chat history loading errors', async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        })
        .mockRejectedValueOnce(new Error('Failed to load chat history'));

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
      });

      act(() => {
        screen.getByTestId('select-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('selected-document')).toHaveTextContent('test.csv');
        expect(screen.getByTestId('error')).toHaveTextContent('Failed to load chat history: Failed to load chat history');
      });
    });

    test('handles 404 for chat history (no history exists)', async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 404
        });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
      });

      act(() => {
        screen.getByTestId('select-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('selected-document')).toHaveTextContent('test.csv');
        expect(screen.getByTestId('chat-messages')).toHaveTextContent('0');
      });
    });
  });

  describe('Chat Message Management', () => {
    test('adds chat message to history', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDocuments
      });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
      });

      act(() => {
        screen.getByTestId('add-message-btn').click();
      });

      expect(screen.getByTestId('chat-messages')).toHaveTextContent('1');
    });

    test('updates document last_chat_activity when message is added', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDocuments
      });

      const TestComponentWithDocuments = () => {
        const { documents, addChatMessage } = useDocumentContext();
        
        return (
          <div>
            <div data-testid="document-activity">
              {documents.find(d => d.file_id === '1')?.last_chat_activity || 'none'}
            </div>
            <button 
              onClick={() => addChatMessage('1', { 
                message: 'test', 
                sender: 'user', 
                timestamp: '2024-01-15T12:00:00Z' 
              })} 
              data-testid="add-message-btn"
            >
              Add Message
            </button>
          </div>
        );
      };

      render(
        <DocumentProvider>
          <TestComponentWithDocuments />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('document-activity')).toHaveTextContent('none');
      });

      act(() => {
        screen.getByTestId('add-message-btn').click();
      });

      expect(screen.getByTestId('document-activity')).toHaveTextContent('2024-01-15T12:00:00Z');
    });

    test('updates has_charts when chart message is added', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDocuments
      });

      const TestComponentWithCharts = () => {
        const { documents, addChatMessage } = useDocumentContext();
        
        return (
          <div>
            <div data-testid="document-has-charts">
              {documents.find(d => d.file_id === '1')?.has_charts.toString() || 'false'}
            </div>
            <button 
              onClick={() => addChatMessage('1', { 
                message: 'Here is a chart', 
                sender: 'ai', 
                timestamp: '2024-01-15T12:00:00Z',
                chart_data: 'http://example.com/chart.png'
              })} 
              data-testid="add-chart-message-btn"
            >
              Add Chart Message
            </button>
          </div>
        );
      };

      render(
        <DocumentProvider>
          <TestComponentWithCharts />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('document-has-charts')).toHaveTextContent('false');
      });

      act(() => {
        screen.getByTestId('add-chart-message-btn').click();
      });

      expect(screen.getByTestId('document-has-charts')).toHaveTextContent('true');
    });

    test('clears chat history', async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        })
        .mockResolvedValueOnce({
          ok: true
        });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
      });

      // Add a message first
      act(() => {
        screen.getByTestId('add-message-btn').click();
      });

      expect(screen.getByTestId('chat-messages')).toHaveTextContent('1');

      // Clear history
      act(() => {
        screen.getByTestId('clear-history-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('chat-messages')).toHaveTextContent('0');
      });

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/chat-history/1', {
        method: 'DELETE'
      });
    });
  });

  describe('Data Transformation', () => {
    test('transforms API data to match Document interface', async () => {
      const apiResponse = [
        {
          file_id: '1',
          filename: 'test.csv',
          // Missing some fields that should get defaults
        }
      ];

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => apiResponse
      });

      const TestComponentWithTransformation = () => {
        const { documents } = useDocumentContext();
        const doc = documents[0];
        
        return (
          <div>
            <div data-testid="upload-date">{doc?.upload_date || 'none'}</div>
            <div data-testid="total-rows">{doc?.total_rows || 0}</div>
            <div data-testid="status">{doc?.status || 'none'}</div>
            <div data-testid="has-charts">{doc?.has_charts?.toString() || 'false'}</div>
          </div>
        );
      };

      render(
        <DocumentProvider>
          <TestComponentWithTransformation />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('upload-date')).not.toHaveTextContent('none');
        expect(screen.getByTestId('total-rows')).toHaveTextContent('0');
        expect(screen.getByTestId('status')).toHaveTextContent('uploaded');
        expect(screen.getByTestId('has-charts')).toHaveTextContent('false');
      });
    });

    test('transforms chat messages to match ChatMessage interface', async () => {
      const apiChatHistory = {
        messages: [
          {
            message: 'Hello',
            sender: 'user',
            timestamp: '2024-01-15T10:30:00Z'
            // Missing id field
          }
        ]
      };

      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => apiChatHistory
        });

      const TestComponentWithChatTransformation = () => {
        const { selectDocument, getChatMessages } = useDocumentContext();
        const messages = getChatMessages('1');
        const message = messages[0];
        
        return (
          <div>
            <div data-testid="message-id">{message?.id || 'none'}</div>
            <div data-testid="file-id">{message?.file_id || 'none'}</div>
            <button 
              onClick={() => selectDocument({ file_id: '1', filename: 'test.csv' })} 
              data-testid="select-btn"
            >
              Select
            </button>
          </div>
        );
      };

      render(
        <DocumentProvider>
          <TestComponentWithChatTransformation />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('message-id')).toHaveTextContent('none');
      });

      act(() => {
        screen.getByTestId('select-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('message-id')).not.toHaveTextContent('none');
        expect(screen.getByTestId('file-id')).toHaveTextContent('1');
      });
    });
  });

  describe('Connection Status Management', () => {
    test('updates connection status based on error types', async () => {
      fetch.mockRejectedValueOnce(new Error('fetch error'));

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('connection-status')).toHaveTextContent('disconnected');
      });
    });

    test('resets connection status on successful request', async () => {
      fetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        });

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('connection-status')).toHaveTextContent('disconnected');
      });

      act(() => {
        screen.getByTestId('refresh-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('connection-status')).toHaveTextContent('connected');
      });
    });
  });

  describe('Error Recovery', () => {
    test('clears error when selecting new document', async () => {
      fetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockDocuments
        })
        .mockRejectedValueOnce(new Error('Chat history error'));

      render(
        <DocumentProvider>
          <TestComponent />
        </DocumentProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('documents-count')).toHaveTextContent('2');
      });

      // First selection causes error
      act(() => {
        screen.getByTestId('select-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('error')).not.toHaveTextContent('none');
      });

      // Mock successful chat history for second selection
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockChatHistory
      });

      // Second selection should clear error
      act(() => {
        screen.getByTestId('select-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('none');
      });
    });
  });
});