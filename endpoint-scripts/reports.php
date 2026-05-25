<?php
$input = file_get_contents("php://input");
$contentType = $_SERVER['CONTENT_TYPE'] ?? '';

$decoded = json_decode($input, true);
$file = __DIR__ . "/reports.json";

if ($decoded === null) {
    file_put_contents($file, json_encode([
        "content_type" => $contentType,
        "results_id" => -1,
        "raw_body" => $input
    ]) . "\n", FILE_APPEND | LOCK_EX);

    http_response_code(204);
    exit;
}

$entries = [];

if (is_array($decoded)) {
    $isAssoc = array_keys($decoded) !== range(0, count($decoded) - 1);

    if ($isAssoc && isset($decoded['type'])) {
        $entries = [$decoded];
    } else {
        $entries = $decoded;
    }
} elseif (isset($decoded['csp-report'])) {
    $entries = [$decoded['csp-report']];
}

function extract_results_id($url) {
    if (!$url) return null;

    $parts = parse_url($url);
    if (!isset($parts['query'])) return null;

    parse_str($parts['query'], $query);
    return $query['results_id'] ?? null;
}

foreach ($entries as $entry) {

    if (isset($entry['body'])) {
        // report-to
        $doc = $entry['body']['documentURL'] ?? null;
        $url = $entry['url'] ?? null;
        $type = $entry['type'] ?? 'csp-violation';
    } else {
        // report-uri
        $doc = $entry['document-uri'] ?? null;
        $url = null;
        $type = 'csp-violation';
    }

    $results_id = extract_results_id($doc) ?? extract_results_id($url) ?? -1;

    $data = [
        "content_type" => $contentType,
        "results_id" => $results_id,
        "type" => $type,
        "report" => $entry
    ];

    file_put_contents($file, json_encode($data) . "\n", FILE_APPEND | LOCK_EX);
}

http_response_code(204);
?>