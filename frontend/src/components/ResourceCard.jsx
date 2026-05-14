function ResourceCard({ resource, onClick }) {
  const thumbnailUrl = resource.content || '';
  const hasImage = resource.file_type === 'image' && thumbnailUrl.startsWith('data:image/');

  return (
    <div className="resource-card" onClick={onClick}>
      <div className="resource-thumbnail">
        {hasImage ? (
          <img
            src={thumbnailUrl}
            alt={resource.file_name}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              borderRadius: '8px'
            }}
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.parentElement.innerHTML = '<span style="font-size: 2rem;">📷</span>';
            }}
          />
        ) : resource.file_type === 'image' ? (
          <span className="doc-icon">📷</span>
        ) : (
          <span className="doc-icon">📄</span>
        )}
      </div>
      <div className="resource-info">
        <div className="resource-name">{resource.file_name}</div>
        {resource.scene_tags && (
          <div className="resource-tags">
            <span className="tag">{resource.scene_tags}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResourceCard;
