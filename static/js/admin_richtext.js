// Load TinyMCE dynamically from CDN inside Django Admin
(function() {
    document.addEventListener('DOMContentLoaded', function() {
        var script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/tinymce/6.8.2/tinymce.min.js';
        script.referrerPolicy = 'origin';
        script.onload = function() {
            // Target all textarea fields in the admin page
            tinymce.init({
                selector: 'textarea',
                height: 350,
                menubar: false,
                plugins: 'advlist autolink lists link image charmap preview anchor searchreplace visualblocks code fullscreen insertdatetime media table code help wordcount',
                toolbar: 'undo redo | blocks | bold italic backcolor | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | removeformat | code help',
                content_style: 'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 14px; margin: 10px; }'
            });
        };
        document.head.appendChild(script);
    });
})();
