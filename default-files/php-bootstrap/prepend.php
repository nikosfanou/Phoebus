<?php
$uri = $_SERVER['REQUEST_URI'] ?? '';

// skip for endpoints
if (strncmp($uri, '/api/', 5) === 0) {
    return;
}

ob_start();

$script = $_SERVER['SCRIPT_FILENAME'] ?? '';
$base   = basename($script);

// Always
require_once __DIR__ . '/env.php';

// Deployment-specific logic
require_once __DIR__ . '/runtime.php';

// Skip runtime logic for files starting with underscore
if ($base !== '' && $base[0] === '_') {
    header_remove();
    ob_clean();
}
?>