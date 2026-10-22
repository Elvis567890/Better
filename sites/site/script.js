// Simple interaction for the download button
document.addEventListener('DOMContentLoaded', function () {
    const downloadBtn = document.querySelector('.btn.download');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function (e) {
            e.preventDefault();
            // Replace the URL below with the actual download link
            const downloadUrl = 'https://example.com/devtime-pro-latest.zip';
            window.location.href = downloadUrl;
        });
    }
});