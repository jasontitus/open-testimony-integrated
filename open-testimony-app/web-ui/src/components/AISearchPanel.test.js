import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AISearchPanel from './AISearchPanel';

// Mock dependencies
jest.mock('../auth', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    put: jest.fn(),
  },
}));

// Mock axios — define mock fns inside factory, expose via _instance
jest.mock('axios', () => {
  const instance = { get: jest.fn(), post: jest.fn() };
  return { create: jest.fn(() => instance), _instance: instance };
});

jest.mock('./AISearchResultCard', () => {
  return function MockAISearchResultCard({ result, onClick, selectable, selected, onToggleSelect }) {
    return (
      <div data-testid={`result-card-${result.video_id}-${result.timestamp_ms || result.start_ms}`}>
        <span>{result.video_id.slice(0, 8)}...</span>
        <button onClick={() => onClick(result)} data-testid={`play-${result.timestamp_ms || result.start_ms}`}>
          Play
        </button>
        {selectable && (
          <button onClick={() => onToggleSelect(result)} data-testid={`select-${result.timestamp_ms || result.start_ms}`}>
            {selected ? 'Deselect' : 'Select'}
          </button>
        )}
      </div>
    );
  };
});

jest.mock('./QuickTagMenu', () => {
  return function MockQuickTagMenu({ videoIds, inline, onTagsChanged, onCategoryChanged, onClose }) {
    return (
      <div data-testid={inline ? 'inline-tag-menu' : 'popup-tag-menu'}>
        <span>Tags for {videoIds.join(', ')}</span>
        {onTagsChanged && (
          <button
            data-testid="mock-add-tag"
            onClick={() => onTagsChanged(videoIds[0], ['protest', 'new-tag'])}
          >
            Add Tag
          </button>
        )}
        {onCategoryChanged && (
          <button
            data-testid="mock-set-category"
            onClick={() => onCategoryChanged(videoIds[0], 'incident')}
          >
            Set Category
          </button>
        )}
      </div>
    );
  };
});

import { useAuth } from '../auth';
import api from '../api';

// Access the mock axios instance created inside the jest.mock factory
const axios = require('axios');
const mockAiApiGet = axios._instance.get;
const mockAiApiPost = axios._instance.post;

// Helper to build search results
const makeResult = (videoId, timestampMs, score = 0.8, extras = {}) => ({
  video_id: videoId,
  timestamp_ms: timestampMs,
  score,
  segment_text: `Transcript at ${timestampMs}ms`,
  thumbnail_url: `/thumbnails/${videoId}/${timestampMs}.jpg`,
  ...extras,
});

const VIDEO_A = 'aaaaaaaa-1111-1111-1111-111111111111';
const VIDEO_B = 'bbbbbbbb-2222-2222-2222-222222222222';

const multiVideoResults = [
  makeResult(VIDEO_A, 5000, 0.95),
  makeResult(VIDEO_A, 12000, 0.80),
  makeResult(VIDEO_A, 25000, 0.60),
  makeResult(VIDEO_B, 3000, 0.90),
  makeResult(VIDEO_B, 18000, 0.70),
];

const defaultProps = {
  availableTags: ['protest', 'arrest'],
  tagCounts: [{ tag: 'protest', count: 5 }],
  onVideoTagsChanged: jest.fn(),
  onResultClick: jest.fn(),
};

// Helper to trigger a search and inject results
async function performSearch(results) {
  mockAiApiGet.mockImplementation((url) => {
    if (url === '/indexing/status') {
      return Promise.resolve({ data: { completed: 5, processing: 1, pending: 0 } });
    }
    // Search endpoint
    return Promise.resolve({ data: { results } });
  });

  const input = screen.getByPlaceholderText("Describe what you're looking for...");
  await userEvent.type(input, 'test query');
  fireEvent.submit(input.closest('form'));

  // Wait for results to appear
  await waitFor(() => {
    expect(screen.getByText(/result/)).toBeInTheDocument();
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({ user: { role: 'admin' } });

  // Default API mocks
  api.get.mockImplementation((url) => {
    if (url.includes('/url')) {
      return Promise.resolve({ data: { url: 'https://example.com/video.mp4' } });
    }
    // Video detail
    return Promise.resolve({
      data: {
        id: url.split('/')[2],
        incident_tags: ['protest'],
        category: 'incident',
        notes: 'Existing notes',
        location_description: 'Downtown',
      },
    });
  });
  api.put.mockResolvedValue({ data: { status: 'success' } });

  // Mock the aiApi calls (indexing status + search)
  mockAiApiGet.mockImplementation((url) => {
    if (url === '/indexing/status') {
      return Promise.resolve({ data: { completed: 5, processing: 1, pending: 0 } });
    }
    return Promise.resolve({ data: { results: [] } });
  });
  mockAiApiPost.mockResolvedValue({ data: { results: [] } });
});

describe('AISearchPanel', () => {
  // --- Result Grouping ---

  describe('result grouping', () => {
    test('groups results by video_id and shows correct count', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Should show grouped count
      expect(screen.getByText(/5 results across 2 videos/)).toBeInTheDocument();
    });

    test('shows match count badge per group', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Video A has 3 matches, Video B has 2
      expect(screen.getByText('3 matches')).toBeInTheDocument();
      expect(screen.getByText('2 matches')).toBeInTheDocument();
    });

    test('single-match group shows singular "match"', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch([makeResult(VIDEO_A, 5000, 0.85)]);

      expect(screen.getByText('1 match')).toBeInTheDocument();
    });

    test('shows video_id prefix in group header', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      expect(screen.getByText('aaaaaaaa...')).toBeInTheDocument();
      expect(screen.getByText('bbbbbbbb...')).toBeInTheDocument();
    });

    test('shows best score in group header', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Video A best score is 95%, Video B best score is 90%
      expect(screen.getByText('95%')).toBeInTheDocument();
      expect(screen.getByText('90%')).toBeInTheDocument();
    });
  });

  // --- Expand/Collapse ---

  describe('expand/collapse', () => {
    test('individual result cards are hidden by default (collapsed)', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Individual result cards should NOT be rendered when collapsed
      expect(screen.queryByTestId(`result-card-${VIDEO_A}-5000`)).not.toBeInTheDocument();
      expect(screen.queryByTestId(`result-card-${VIDEO_A}-12000`)).not.toBeInTheDocument();
    });

    test('clicking chevron expands to show individual result cards', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Find and click the first expand button (chevron)
      const expandButtons = screen.getAllByTitle('Expand matches');
      fireEvent.click(expandButtons[0]);

      // Now individual cards for Video A should be visible
      await waitFor(() => {
        expect(screen.getByTestId(`result-card-${VIDEO_A}-5000`)).toBeInTheDocument();
        expect(screen.getByTestId(`result-card-${VIDEO_A}-12000`)).toBeInTheDocument();
        expect(screen.getByTestId(`result-card-${VIDEO_A}-25000`)).toBeInTheDocument();
      });

      // But Video B should still be collapsed
      expect(screen.queryByTestId(`result-card-${VIDEO_B}-3000`)).not.toBeInTheDocument();
    });

    test('clicking chevron again collapses the group', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      const expandButtons = screen.getAllByTitle('Expand matches');
      // Expand
      fireEvent.click(expandButtons[0]);
      await waitFor(() => {
        expect(screen.getByTestId(`result-card-${VIDEO_A}-5000`)).toBeInTheDocument();
      });

      // Collapse
      const collapseButtons = screen.getAllByTitle('Collapse matches');
      fireEvent.click(collapseButtons[0]);

      await waitFor(() => {
        expect(screen.queryByTestId(`result-card-${VIDEO_A}-5000`)).not.toBeInTheDocument();
      });
    });

    test('expanded group shows label about individual matches', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      const expandButtons = screen.getAllByTitle('Expand matches');
      fireEvent.click(expandButtons[0]);

      await waitFor(() => {
        expect(screen.getByText(/Individual matches/)).toBeInTheDocument();
      });
    });
  });

  // --- Video-level click (group header) ---

  describe('video-level click', () => {
    test('clicking group header opens inline player', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Click the group header text (video_id)
      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        // Player should be visible with video element or loading
        expect(api.get).toHaveBeenCalledWith(`/videos/${VIDEO_A}/url`);
        expect(api.get).toHaveBeenCalledWith(`/videos/${VIDEO_A}`);
      });
    });

    test('clicking group header fetches video detail for annotations', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        // Should show annotation panel with inline tag menu
        expect(screen.getByTestId('inline-tag-menu')).toBeInTheDocument();
      });
    });

    test('annotation panel shows notes and location fields', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        // Notes field pre-populated with existing notes
        const notesField = screen.getByPlaceholderText('Add notes about this video...');
        expect(notesField).toBeInTheDocument();
        expect(notesField.value).toBe('Existing notes');

        // Location field pre-populated
        const locationField = screen.getByPlaceholderText('Location description...');
        expect(locationField).toBeInTheDocument();
        expect(locationField.value).toBe('Downtown');
      });
    });

    test('annotation panel hidden for non-staff users', async () => {
      useAuth.mockReturnValue({ user: { role: 'viewer' } });

      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith(`/videos/${VIDEO_A}/url`);
      });

      // No annotation panel
      expect(screen.queryByTestId('inline-tag-menu')).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText('Add notes about this video...')).not.toBeInTheDocument();
    });
  });

  // --- Annotation Save ---

  describe('annotation save', () => {
    test('save button calls PUT with notes and location', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Add notes about this video...')).toBeInTheDocument();
      });

      // Edit notes
      const notesField = screen.getByPlaceholderText('Add notes about this video...');
      await userEvent.clear(notesField);
      await userEvent.type(notesField, 'Updated notes');

      // Edit location
      const locationField = screen.getByPlaceholderText('Location description...');
      await userEvent.clear(locationField);
      await userEvent.type(locationField, 'Uptown');

      // Click save
      fireEvent.click(screen.getByText('Save'));

      await waitFor(() => {
        expect(api.put).toHaveBeenCalledWith(
          `/videos/${VIDEO_A}/annotations/web`,
          {
            notes: 'Updated notes',
            location_description: 'Uptown',
          }
        );
      });
    });

    test('shows "Saved" confirmation after successful save', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        expect(screen.getByText('Save')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Save'));

      await waitFor(() => {
        expect(screen.getByText('Saved')).toBeInTheDocument();
      });
    });

    test('shows error on save failure', async () => {
      api.put.mockRejectedValueOnce({
        response: { data: { detail: 'Permission denied' } },
      });

      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        expect(screen.getByText('Save')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Save'));

      await waitFor(() => {
        expect(screen.getByText('Permission denied')).toBeInTheDocument();
      });
    });

    test('tag changes from inline menu propagate to results', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        expect(screen.getByTestId('mock-add-tag')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('mock-add-tag'));

      expect(defaultProps.onVideoTagsChanged).toHaveBeenCalledWith(
        VIDEO_A,
        ['protest', 'new-tag']
      );
    });
  });

  // --- Close player ---

  describe('player controls', () => {
    test('close button hides player and annotations', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('aaaaaaaa...'));

      await waitFor(() => {
        expect(screen.getByTestId('inline-tag-menu')).toBeInTheDocument();
      });

      // The video_id appears in both the player header and the group list.
      // Find the player header by looking for the font-mono span inside overflow-y-auto panel.
      const allVideoIdSpans = screen.getAllByText('aaaaaaaa...');
      // The player header span has class "text-xs text-gray-400 font-mono"
      const playerHeader = allVideoIdSpans.find(el =>
        el.closest('.flex.items-center.justify-between')?.closest('.overflow-y-auto')
      );
      // Get the close button (X) from the same header row
      const headerRow = playerHeader.closest('.flex.items-center.justify-between');
      const closeBtn = within(headerRow).getAllByRole('button')[0];
      fireEvent.click(closeBtn);

      await waitFor(() => {
        expect(screen.queryByTestId('inline-tag-menu')).not.toBeInTheDocument();
      });
    });
  });

  // --- Bulk selection ---

  describe('bulk selection', () => {
    test('select mode shows checkboxes on group headers', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Enter select mode
      fireEvent.click(screen.getByText('Select'));

      // Should show Cancel instead of Select
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    test('cancel exits select mode', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      fireEvent.click(screen.getByText('Select'));
      expect(screen.getByText('Cancel')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Cancel'));
      expect(screen.getByText('Select')).toBeInTheDocument();
    });
  });

  // --- Search modes ---

  describe('search modes', () => {
    test('renders all four search mode buttons', () => {
      render(<AISearchPanel {...defaultProps} />);

      expect(screen.getByText('Visual (Text)')).toBeInTheDocument();
      expect(screen.getByText('Visual (Image)')).toBeInTheDocument();
      expect(screen.getByText('Transcript (Semantic)')).toBeInTheDocument();
      expect(screen.getByText('Transcript (Exact)')).toBeInTheDocument();
    });

    test('shows empty state before search', () => {
      render(<AISearchPanel {...defaultProps} />);

      expect(screen.getByText('Search across all indexed videos using AI')).toBeInTheDocument();
    });

    test('switching search mode clears results', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      expect(screen.getByText(/5 results/)).toBeInTheDocument();

      // Switch mode
      fireEvent.click(screen.getByText('Transcript (Semantic)'));

      expect(screen.queryByText(/5 results/)).not.toBeInTheDocument();
    });
  });

  // --- Enrichment ---

  describe('result enrichment', () => {
    test('fetches video details to enrich tags and category', async () => {
      render(<AISearchPanel {...defaultProps} />);
      await performSearch(multiVideoResults);

      // Should have fetched details for both unique video IDs
      await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith(`/videos/${VIDEO_A}`);
        expect(api.get).toHaveBeenCalledWith(`/videos/${VIDEO_B}`);
      });
    });
  });
});
