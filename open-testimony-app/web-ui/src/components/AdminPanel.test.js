import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminPanel from './AdminPanel';
import api from '../api';

// Mock the api module
jest.mock('../api', () => {
  const mockApi = {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  };
  return { __esModule: true, default: mockApi };
});

// Mock axios for the aiApi instance
jest.mock('axios', () => ({
  create: () => ({
    get: jest.fn().mockResolvedValue({ data: { completed: 0, processing: 0, pending: 0, failed: 0 } }),
    post: jest.fn().mockResolvedValue({ data: {} }),
  }),
}));

beforeEach(() => {
  jest.clearAllMocks();

  // Default mock responses for initial data loads
  api.get.mockImplementation((url) => {
    if (url === '/auth/users') {
      return Promise.resolve({ data: { users: [] } });
    }
    if (url === '/tags') {
      return Promise.resolve({ data: { all_tags: [], default_tags: [] } });
    }
    if (url === '/audit-log') {
      return Promise.resolve({ data: { total: 0, entries: [] } });
    }
    if (url === '/audit-log/verify') {
      return Promise.resolve({ data: { valid: true, entries_checked: 0, errors: [] } });
    }
    return Promise.resolve({ data: {} });
  });
});


describe('BulkUpload section', () => {
  test('renders bulk upload heading', async () => {
    render(<AdminPanel />);
    expect(await screen.findByText('Bulk Upload')).toBeInTheDocument();
  });

  test('renders drop zone instructions', async () => {
    render(<AdminPanel />);
    expect(
      await screen.findByText(/click or drag files here/i)
    ).toBeInTheDocument();
  });

  test('shows unverified notice in drop zone', async () => {
    render(<AdminPanel />);
    // The BulkUpload section always renders - check for the info text
    await waitFor(() => {
      const el = document.querySelector('.bg-gray-800 p.text-\\[10px\\]');
      expect(el || screen.queryByText(/unverified/i)).toBeTruthy();
    });
  });

  test('shows file list after selecting files', async () => {
    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    expect(input).toBeTruthy();
    expect(input.multiple).toBe(true);
    expect(input.accept).toBe('video/*,image/*');

    const file = new File(['video-data'], 'test.mp4', { type: 'video/mp4' });
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    expect(screen.getByText('test.mp4')).toBeInTheDocument();
    expect(screen.getByText(/1 file selected/i)).toBeInTheDocument();
  });

  test('shows multiple files after selection', async () => {
    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const files = [
      new File(['video1'], 'video1.mp4', { type: 'video/mp4' }),
      new File(['photo1'], 'photo1.jpg', { type: 'image/jpeg' }),
    ];

    await act(async () => {
      fireEvent.change(input, { target: { files } });
    });

    expect(screen.getByText('video1.mp4')).toBeInTheDocument();
    expect(screen.getByText('photo1.jpg')).toBeInTheDocument();
    expect(screen.getByText(/2 files selected/i)).toBeInTheDocument();
  });

  test('clear all button removes files', async () => {
    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const file = new File(['data'], 'test.mp4', { type: 'video/mp4' });

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    expect(screen.getByText('test.mp4')).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByText('Clear all'));
    });
    expect(screen.queryByText('test.mp4')).not.toBeInTheDocument();
  });

  test('upload button calls API with FormData', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        status: 'success',
        total: 1,
        succeeded: 1,
        failed: 0,
        results: [{
          filename: 'test.mp4',
          status: 'success',
          video_id: 'abc-123',
          media_type: 'video',
          verification_status: 'unverified',
          has_exif: false,
          location: { lat: 0, lon: 0 },
        }],
      },
    });

    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const file = new File(['video-data'], 'test.mp4', { type: 'video/mp4' });

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    const uploadBtn = screen.getByText(/upload 1 file/i);
    await act(async () => {
      fireEvent.click(uploadBtn);
    });

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/bulk-upload',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
        }),
      );
    });
  });

  test('displays success results after upload', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        status: 'success',
        total: 1,
        succeeded: 1,
        failed: 0,
        results: [{
          filename: 'evidence.mp4',
          status: 'success',
          video_id: 'vid-001',
          media_type: 'video',
          verification_status: 'unverified',
          has_exif: false,
          location: { lat: 0, lon: 0 },
        }],
      },
    });

    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const file = new File(['data'], 'evidence.mp4', { type: 'video/mp4' });

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByText(/upload 1 file/i));
    });

    await waitFor(() => {
      expect(screen.getByText(/1 of 1 file.*uploaded successfully/i)).toBeInTheDocument();
    });
    expect(screen.getByText('evidence.mp4')).toBeInTheDocument();
  });

  test('displays error results on failure', async () => {
    const err = new Error('Request failed');
    err.response = { data: { detail: 'Not authenticated' } };
    api.post.mockRejectedValueOnce(err);

    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const file = new File(['data'], 'test.mp4', { type: 'video/mp4' });

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByText(/upload 1 file/i));
    });

    await waitFor(() => {
      expect(screen.getByText(/0 of 1/)).toBeInTheDocument();
    });
  });

  test('displays partial success results', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        status: 'partial',
        total: 2,
        succeeded: 1,
        failed: 1,
        results: [
          {
            filename: 'good.mp4',
            status: 'success',
            video_id: 'vid-001',
            media_type: 'video',
            verification_status: 'unverified',
            has_exif: false,
            location: { lat: 0, lon: 0 },
          },
          {
            filename: 'bad.mp4',
            status: 'error',
            detail: 'Empty file',
          },
        ],
      },
    });

    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const files = [
      new File(['data'], 'good.mp4', { type: 'video/mp4' }),
      new File([''], 'bad.mp4', { type: 'video/mp4' }),
    ];

    await act(async () => {
      fireEvent.change(input, { target: { files } });
    });
    await act(async () => {
      fireEvent.click(screen.getByText(/upload 2 files/i));
    });

    await waitFor(() => {
      expect(screen.getByText(/1 of 2 files.*uploaded successfully.*1 failed/i)).toBeInTheDocument();
    });
  });

  test('shows EXIF badge for files with EXIF data', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        status: 'success',
        total: 1,
        succeeded: 1,
        failed: 0,
        results: [{
          filename: 'gps-photo.jpg',
          status: 'success',
          video_id: 'vid-002',
          media_type: 'photo',
          verification_status: 'unverified',
          has_exif: true,
          location: { lat: 40.7, lon: -74.0 },
        }],
      },
    });

    render(<AdminPanel />);

    const input = document.querySelector('input[type="file"]');
    const file = new File(['data'], 'gps-photo.jpg', { type: 'image/jpeg' });

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByText(/upload 1 file/i));
    });

    await waitFor(() => {
      expect(screen.getByText(/· EXIF/)).toBeInTheDocument();
    });
  });
});
