<?php
// Webhook proxy script for baseshinomontaz.store
// This script forwards Telegram webhook requests to the current VPS URL

// Current VPS URL (update this when VPS URL changes)
$vps_url = "https://8867069a-d008-4da6-8b30-bdb8e855fcb4.preview.emergentagent.com";

// Log file for debugging
$log_file = "webhook_log.txt";

// Get the input data from Telegram
$input = file_get_contents('php://input');
$headers = getallheaders();

// Log the request
$log_entry = date('[Y-m-d H:i:s] ') . "Received webhook request\n";
$log_entry .= "Input size: " . strlen($input) . " bytes\n";
$log_entry .= "Headers: " . json_encode($headers) . "\n";

// Forward the request to the actual VPS
$target_url = $vps_url . "/api/webhook";

// Initialize cURL
$ch = curl_init();

// Set cURL options
curl_setopt($ch, CURLOPT_URL, $target_url);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $input);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);

// Set headers
$forward_headers = array();
foreach ($headers as $key => $value) {
    if (stripos($key, 'content-') === 0 || stripos($key, 'x-telegram-') === 0) {
        $forward_headers[] = $key . ': ' . $value;
    }
}
$forward_headers[] = 'Content-Type: application/json';

curl_setopt($ch, CURLOPT_HTTPHEADER, $forward_headers);

// Execute the request
$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_error = curl_error($ch);

curl_close($ch);

// Log the response
$log_entry .= "Target URL: " . $target_url . "\n";
$log_entry .= "Response code: " . $http_code . "\n";
$log_entry .= "Response: " . $response . "\n";
if ($curl_error) {
    $log_entry .= "CURL Error: " . $curl_error . "\n";
}
$log_entry .= "---\n";

// Write to log file
file_put_contents($log_file, $log_entry, FILE_APPEND);

// Return response to Telegram
if ($response) {
    echo $response;
} else {
    echo json_encode(["status" => "error", "message" => "Failed to forward request"]);
}
?>