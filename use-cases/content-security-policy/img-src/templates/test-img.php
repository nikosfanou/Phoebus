<head></head>
<body>
    <img src="{IMG_URL}" />
    
    <script>
    (function () {
        const img = new Image();
        img.id = '{AUTO.ID}';
        img.src = '{IMG_URL}';
        document.body.appendChild(img);
    })();
    </script>
</body>