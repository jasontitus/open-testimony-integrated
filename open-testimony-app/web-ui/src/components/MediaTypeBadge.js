import React from 'react';
import { Camera, Video } from 'lucide-react';

export default function MediaTypeBadge({ mediaType }) {
  if (mediaType === 'photo') {
    return (
      <span className="flex items-center gap-1 text-[10px] text-gray-400 font-medium uppercase">
        <Camera size={10} />
        Photo
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[10px] text-gray-400 font-medium uppercase">
      <Video size={10} />
      Video
    </span>
  );
}
