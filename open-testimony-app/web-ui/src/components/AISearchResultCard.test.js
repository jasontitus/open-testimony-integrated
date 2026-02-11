import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AISearchResultCard from './AISearchResultCard';

// Mock dependencies
jest.mock('../auth', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../api', () => ({
  __esModule: true,
  default: {
    get: jest.fn().mockResolvedValue({ data: { incident_tags: [] } }),
    put: jest.fn().mockResolvedValue({ data: {} }),
  },
}));

jest.mock('./QuickTagMenu', () => {
  return function MockQuickTagMenu({ videoIds, onClose, onTagsChanged }) {
    return (
      <div data-testid="quick-tag-menu">
        <span>Mock QuickTagMenu for {videoIds.join(', ')}</span>
        <button onClick={onClose}>Close Menu</button>
      </div>
    );
  };
});

import { useAuth } from '../auth';

const baseResult = {
  video_id: 'abc12345-1234-1234-1234-123456789012',
  timestamp_ms: 5000,
  score: 0.85,
  segment_text: 'This is test transcript text',
  thumbnail_url: '/thumbnails/abc/5000.jpg',
};

const defaultProps = {
  result: baseResult,
  mode: 'visual_text',
  onClick: jest.fn(),
  availableTags: ['protest', 'arrest'],
  tagCounts: [{ tag: 'protest', count: 5 }],
  onVideoTagsChanged: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('AISearchResultCard', () => {
  test('renders result info correctly', () => {
    useAuth.mockReturnValue({ user: { role: 'viewer' } });

    render(<AISearchResultCard {...defaultProps} />);

    expect(screen.getByText(/abc12345/)).toBeInTheDocument();
    expect(screen.getByText('Frame at 0:05')).toBeInTheDocument();
    expect(screen.getByText(/This is test transcript text/)).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  test('shows tag button for staff users', () => {
    useAuth.mockReturnValue({ user: { role: 'staff' } });

    render(<AISearchResultCard {...defaultProps} />);

    expect(screen.getByTitle('Quick Tag')).toBeInTheDocument();
  });

  test('shows tag button for admin users', () => {
    useAuth.mockReturnValue({ user: { role: 'admin' } });

    render(<AISearchResultCard {...defaultProps} />);

    expect(screen.getByTitle('Quick Tag')).toBeInTheDocument();
  });

  test('hides tag button for non-staff users', () => {
    useAuth.mockReturnValue({ user: { role: 'viewer' } });

    render(<AISearchResultCard {...defaultProps} />);

    expect(screen.queryByTitle('Quick Tag')).not.toBeInTheDocument();
  });

  test('clicking tag button opens QuickTagMenu', async () => {
    useAuth.mockReturnValue({ user: { role: 'staff' } });

    render(<AISearchResultCard {...defaultProps} />);

    fireEvent.click(screen.getByTitle('Quick Tag'));

    await waitFor(() => {
      expect(screen.getByTestId('quick-tag-menu')).toBeInTheDocument();
    });
  });

  test('tag button click does not propagate to card onClick', () => {
    useAuth.mockReturnValue({ user: { role: 'staff' } });

    render(<AISearchResultCard {...defaultProps} />);

    fireEvent.click(screen.getByTitle('Quick Tag'));

    expect(defaultProps.onClick).not.toHaveBeenCalled();
  });

  test('card click fires onClick handler', () => {
    useAuth.mockReturnValue({ user: { role: 'viewer' } });

    render(<AISearchResultCard {...defaultProps} />);

    // Click the card itself (not the tag button)
    fireEvent.click(screen.getByText(/abc12345/));

    expect(defaultProps.onClick).toHaveBeenCalledWith(baseResult);
  });

  test('displays existing incident_tags as pills', () => {
    useAuth.mockReturnValue({ user: { role: 'viewer' } });

    const resultWithTags = {
      ...baseResult,
      incident_tags: ['protest', 'arrest'],
    };

    render(<AISearchResultCard {...defaultProps} result={resultWithTags} />);

    expect(screen.getByText('protest')).toBeInTheDocument();
    expect(screen.getByText('arrest')).toBeInTheDocument();
  });

  test('shows transcript search format (time range)', () => {
    useAuth.mockReturnValue({ user: { role: 'viewer' } });

    const transcriptResult = {
      ...baseResult,
      start_ms: 10000,
      end_ms: 15000,
      timestamp_ms: undefined,
    };

    render(
      <AISearchResultCard
        {...defaultProps}
        result={transcriptResult}
        mode="transcript_semantic"
      />
    );

    expect(screen.getByText(/0:10/)).toBeInTheDocument();
    expect(screen.getByText(/0:15/)).toBeInTheDocument();
  });

  test('shows checkbox in select mode', () => {
    useAuth.mockReturnValue({ user: { role: 'staff' } });

    const onToggle = jest.fn();

    render(
      <AISearchResultCard
        {...defaultProps}
        selectable={true}
        selected={false}
        onToggleSelect={onToggle}
      />
    );

    // There should be a checkbox-like button
    // Click it and verify onToggleSelect is called
    const checkboxes = screen.getAllByRole('button');
    // The first button in selectable mode is the checkbox
    fireEvent.click(checkboxes[0]);

    expect(onToggle).toHaveBeenCalledWith(baseResult);
  });

  test('checkbox click does not propagate to card', () => {
    useAuth.mockReturnValue({ user: { role: 'staff' } });

    const onToggle = jest.fn();

    render(
      <AISearchResultCard
        {...defaultProps}
        selectable={true}
        selected={false}
        onToggleSelect={onToggle}
      />
    );

    const checkboxes = screen.getAllByRole('button');
    fireEvent.click(checkboxes[0]);

    expect(defaultProps.onClick).not.toHaveBeenCalled();
  });
});
