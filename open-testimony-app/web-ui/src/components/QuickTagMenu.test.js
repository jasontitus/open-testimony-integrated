import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import QuickTagMenu from './QuickTagMenu';

// Mock the api module
jest.mock('../api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    put: jest.fn(),
  },
}));

import api from '../api';

const defaultProps = {
  videoIds: ['video-1'],
  availableTags: ['protest', 'arrest', 'traffic-stop', 'use-of-force'],
  tagCounts: [
    { tag: 'protest', count: 10 },
    { tag: 'arrest', count: 5 },
    { tag: 'traffic-stop', count: 3 },
    { tag: 'use-of-force', count: 1 },
  ],
  onClose: jest.fn(),
  onTagsChanged: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
  // Default: video has tag "protest" already
  api.get.mockResolvedValue({ data: { incident_tags: ['protest'] } });
  api.put.mockResolvedValue({ data: {} });
});

describe('QuickTagMenu', () => {
  test('renders loading state then shows tags', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    // Should show header
    expect(screen.getByText('Quick Tag')).toBeInTheDocument();

    // Wait for tags to load
    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });

    // All available tags should appear
    expect(screen.getByText('arrest')).toBeInTheDocument();
    expect(screen.getByText('traffic-stop')).toBeInTheDocument();
    expect(screen.getByText('use-of-force')).toBeInTheDocument();
  });

  test('shows bulk header when multiple videos', async () => {
    render(<QuickTagMenu {...defaultProps} videoIds={['video-1', 'video-2']} />);

    expect(screen.getByText('Tag 2 videos')).toBeInTheDocument();
  });

  test('fetches current tags for each video on mount', async () => {
    render(<QuickTagMenu {...defaultProps} videoIds={['video-1', 'video-2']} />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/videos/video-1');
      expect(api.get).toHaveBeenCalledWith('/videos/video-2');
    });
  });

  test('sorts tags by count (most used first)', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });

    const buttons = screen.getAllByRole('button').filter(
      b => defaultProps.availableTags.includes(b.textContent)
    );
    // protest (10) should be before arrest (5) which is before traffic-stop (3)
    const tagTexts = buttons.map(b => b.textContent);
    expect(tagTexts.indexOf('protest')).toBeLessThan(tagTexts.indexOf('arrest'));
    expect(tagTexts.indexOf('arrest')).toBeLessThan(tagTexts.indexOf('traffic-stop'));
  });

  test('filter input narrows visible tags', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });

    const filterInput = screen.getByPlaceholderText('Filter tags...');
    await userEvent.type(filterInput, 'arr');

    expect(screen.getByText('arrest')).toBeInTheDocument();
    expect(screen.queryByText('protest')).not.toBeInTheDocument();
    expect(screen.queryByText('traffic-stop')).not.toBeInTheDocument();
  });

  test('shows "No tags found" when filter matches nothing', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });

    const filterInput = screen.getByPlaceholderText('Filter tags...');
    await userEvent.type(filterInput, 'zzzznotag');

    expect(screen.getByText('No tags found')).toBeInTheDocument();
  });

  test('clicking an inactive tag adds it and calls PUT', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('arrest')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('arrest'));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/videos/video-1/annotations/web', {
        incident_tags: ['protest', 'arrest'],
      });
      expect(defaultProps.onTagsChanged).toHaveBeenCalledWith(
        'video-1',
        ['protest', 'arrest']
      );
    });
  });

  test('clicking an active tag removes it and calls PUT', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('protest'));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/videos/video-1/annotations/web', {
        incident_tags: [],
      });
      expect(defaultProps.onTagsChanged).toHaveBeenCalledWith('video-1', []);
    });
  });

  test('Escape key calls onClose', async () => {
    render(<QuickTagMenu {...defaultProps} />);

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  test('click outside calls onClose', async () => {
    const { container } = render(
      <div>
        <div data-testid="outside">Outside</div>
        <QuickTagMenu {...defaultProps} />
      </div>
    );

    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });

    fireEvent.mouseDown(screen.getByTestId('outside'));

    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  test('handles API fetch error gracefully', async () => {
    api.get.mockRejectedValue(new Error('Network error'));

    render(<QuickTagMenu {...defaultProps} />);

    // Should still render tags (with empty current tags)
    await waitFor(() => {
      expect(screen.getByText('protest')).toBeInTheDocument();
    });
  });

  test('reverts on save failure', async () => {
    api.put.mockRejectedValue(new Error('Save failed'));
    // After revert, re-fetch returns original tags
    api.get.mockResolvedValue({ data: { incident_tags: ['protest'] } });

    render(<QuickTagMenu {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('arrest')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('arrest'));

    // PUT should be called (and fail)
    await waitFor(() => {
      expect(api.put).toHaveBeenCalled();
    });

    // onTagsChanged should NOT have been called since save failed
    expect(defaultProps.onTagsChanged).not.toHaveBeenCalled();
  });
});
