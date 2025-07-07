<?php
// Webhook proxy script for demondimi.ru
// This script forwards Telegram webhook requests to the local server

// Local server URL (bot runs on port 8001)
$local_url = "http://127.0.0.1:8001";

// Log file for debugging
$log_file = "/var/log/telegram_webhook.log";

// Get the input data from Telegram
$input = file_get_contents('php://input');
$headers = getallheaders();

// Log the request (for debugging)
$log_entry = date('[Y-m-d H:i:s] ') . "Webhook received from Telegram\n";
$log_entry .= "Input size: " . strlen($input) . " bytes\n";
$log_entry .= "User-Agent: " . ($headers['User-Agent'] ?? 'Unknown') . "\n";

// Forward the request to the local server
$target_url = $local_url . "/api/webhook";

// Initialize cURL
$ch = curl_init();

// Set cURL options
curl_setopt($ch, CURLOPT_URL, $target_url);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $input);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);
curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);

// Set headers
$forward_headers = array('Content-Type: application/json');
foreach ($headers as $key => $value) {
    if (stripos($key, 'content-') === 0 || stripos($key, 'x-telegram-') === 0) {
        $forward_headers[] = $key . ': ' . $value;
    }
}

curl_setopt($ch, CURLOPT_HTTPHEADER, $forward_headers);

// Execute the request
$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_error = curl_error($ch);

curl_close($ch);

// Log the response
$log_entry .= "Forwarded to: " . $target_url . "\n";
$log_entry .= "Response code: " . $http_code . "\n";
if ($curl_error) {
    $log_entry .= "CURL Error: " . $curl_error . "\n";
}
$log_entry .= "Success: " . ($http_code == 200 ? "YES" : "NO") . "\n";
$log_entry .= "---\n";

// Write to log file (only if file is writable)
if (is_writable(dirname($log_file))) {
    file_put_contents($log_file, $log_entry, FILE_APPEND | LOCK_EX);
}

// Return response to Telegram
if ($response && $http_code == 200) {
    echo $response;
} else {
    http_response_code(200); // Always return 200 to Telegram
    echo json_encode(["status" => "forwarded", "code" => $http_code]);
}
?>