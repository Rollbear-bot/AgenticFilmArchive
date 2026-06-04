export function formatMessage(content) {
  if (!content) return '';
  return content.replace(/\n/g, '<br>');
}

export function formatTime(date) {
  return new Date(date).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
