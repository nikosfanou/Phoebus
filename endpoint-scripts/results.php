<?php
$input = file_get_contents("php://input");
$contentType = $_SERVER['CONTENT_TYPE'] ?? '';

$data = [];

// 1. Try JSON first (regardless of content-type)
if (!empty($input)) {
    $json = json_decode($input, true);

    if (json_last_error() === JSON_ERROR_NONE && is_array($json)) {
        $data = $json;
    }
}

// 2. Form/query-style body
if (empty($data) && !empty($input)) {
    parse_str($input, $parsed);

    foreach ($parsed as $k => $v) {
        $decoded = json_decode($v, true);
        $data[$k] = (json_last_error() === JSON_ERROR_NONE) ? $decoded : $v;
    }
}

// Store
$entry = [
    "id" => $data['results_id'] ?? -1,
    "results" => $data['result'] ?? null
];

file_put_contents(
    __DIR__ . "/results.json",
    json_encode($entry) . "\n",
    FILE_APPEND | LOCK_EX
);

http_response_code(200);
echo "OK\n";
?>