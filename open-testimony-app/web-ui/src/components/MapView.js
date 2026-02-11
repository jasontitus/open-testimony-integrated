import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { format } from 'date-fns';
import L from 'leaflet';
import SourceBadge from './SourceBadge';
import MediaTypeBadge from './MediaTypeBadge';

export default function MapView({ videos, selectedVideo, onVideoClick }) {
  const mappableVideos = videos.filter(v => v.location !== null && v.location !== undefined && v.location.lat !== null && v.location.lat !== undefined);

  return (
    <div className="h-full w-full z-0">
      <MapContainer center={[0, 0]} zoom={2} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <MarkerClusterGroup>
          {mappableVideos.map(video => (
            <Marker
              key={video.id}
              position={[video.location.lat, video.location.lon]}
              eventHandlers={{ click: () => onVideoClick(video) }}
            >
              <Popup className="custom-popup">
                <div className="text-gray-900 p-1">
                  <p className="font-bold text-xs mb-1">{video.device_id}</p>
                  <p className="text-[10px] text-gray-600 mb-1">{format(new Date(video.timestamp), 'PPpp')}</p>
                  <div className="flex gap-1">
                    <SourceBadge source={video.source} />
                    <MediaTypeBadge mediaType={video.media_type} />
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MarkerClusterGroup>
        <MapUpdater videos={mappableVideos} selectedVideo={selectedVideo} />
      </MapContainer>
    </div>
  );
}

function MapUpdater({ videos, selectedVideo }) {
  const map = useMap();

  // Zoom to selected video
  useEffect(() => {
    if (selectedVideo && selectedVideo.location) {
      map.setView([selectedVideo.location.lat, selectedVideo.location.lon], 16, { animate: true });
    }
  }, [selectedVideo, map]);

  // Fit bounds when video list changes (filter/search) and nothing is selected
  useEffect(() => {
    if (!selectedVideo && videos.length > 0) {
      const bounds = L.latLngBounds(videos.map(v => [v.location.lat, v.location.lon]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16, animate: true });
    }
  }, [videos, selectedVideo, map]);

  return null;
}
