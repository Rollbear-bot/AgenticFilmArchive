import { useState } from 'react';

function ImageThumbnails({ images }) {
  const [collapsed, setCollapsed] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(null);

  if (!images || images.length === 0) return null;

  function openLightbox(index) {
    setLightboxIndex(index);
  }

  function closeLightbox() {
    setLightboxIndex(null);
  }

  function prevImage(e) {
    e.stopPropagation();
    setLightboxIndex((prev) =>
      prev === null ? null : prev > 0 ? prev - 1 : images.length - 1
    );
  }

  function nextImage(e) {
    e.stopPropagation();
    setLightboxIndex((prev) =>
      prev === null ? null : prev < images.length - 1 ? prev + 1 : 0
    );
  }

  return (
    <div className="image-thumbnails">
      <button
        className="image-thumbnails-toggle"
        onClick={() => setCollapsed(!collapsed)}
      >
        {collapsed ? '▶' : '▼'} 📷 相关图片 ({images.length})
      </button>

      {!collapsed && (
        <div className="image-thumbnails-grid">
          {images.map((img, index) => (
            <div
              key={index}
              className="image-thumbnail-item"
              onClick={() => openLightbox(index)}
            >
              <img
                src={img.thumb_url}
                alt={img.file_name || `图片 ${index + 1}`}
                loading="lazy"
              />
              <span className="image-thumbnail-name">
                {img.file_name || `图片 ${index + 1}`}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && (
        <div className="image-lightbox-overlay" onClick={closeLightbox}>
          <button className="image-lightbox-close" onClick={closeLightbox}>
            ✕
          </button>
          <button className="image-lightbox-nav image-lightbox-prev" onClick={prevImage}>
            ‹
          </button>
          <img
            className="image-lightbox-img"
            src={images[lightboxIndex]?.thumb_url}
            alt={images[lightboxIndex]?.file_name || '预览'}
          />
          <button className="image-lightbox-nav image-lightbox-next" onClick={nextImage}>
            ›
          </button>
          <div className="image-lightbox-counter">
            {lightboxIndex + 1} / {images.length}
          </div>
        </div>
      )}
    </div>
  );
}

export default ImageThumbnails;
