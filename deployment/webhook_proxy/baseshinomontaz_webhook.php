<?php
// Production Webhook Proxy for baseshinomontaz.store
// This script receives Telegram webhooks and forwards to the bot backend

// Configuration
$environment = 'production';
$log_enabled = true; // Enable logging for production monitoring

// Backend URLs based on environment
$backend_url = "http://127.0.0.1:8001"; // Local backend on production server

// Get webhook data from Telegram
$input = file_get_contents('php://input');
$headers = getallheaders();

// Optional logging for debugging
if ($log_enabled && !empty($input)) {
    $log_dir = '/var/log/telegram-bot';
    if (!is_dir($log_dir)) {
        mkdir($log_dir, 0755, true);
    }
    
    $log_entry = date('[Y-m-d H:i:s] ') . "Webhook received\n";
    $log_entry .= "Environment: $environment\n";
    $log_entry .= "Input size: " . strlen($input) . " bytes\n";
    $log_entry .= "User-Agent: " . ($headers['User-Agent'] ?? 'Unknown') . "\n";
    
    // Log first 200 chars of input for debugging
    $log_entry .= "Input preview: " . substr($input, 0, 200) . "\n";
    
    file_put_contents($log_dir . '/webhook.log', $log_entry, FILE_APPEND);
}

// Forward to backend
$target_url = $backend_url . "/api/webhook";

$ch = curl_init();
curl_setopt_array($ch, [
    CURLOPT_URL => $target_url,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $input,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_TIMEOUT => 30,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_HTTPHEADER => [
        'Content-Type: application/json',
        'User-Agent: TelegramWebhookProxy/1.0'
    ]
]);

// For production, local connection doesn't need SSL verification
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_error = curl_error($ch);
curl_close($ch);

// Log response if debugging enabled
if ($log_enabled) {
    $log_entry = "Response: HTTP $http_code\n";
    if ($curl_error) {
        $log_entry .= "Error: $curl_error\n";
    }
    $log_entry .= "Success: " . ($http_code == 200 ? "YES" : "NO") . "\n";
    $log_entry .= "Response preview: " . substr($response, 0, 200) . "\n---\n";
    
    file_put_contents('/var/log/telegram-bot/webhook.log', $log_entry, FILE_APPEND);
}

// Return response to Telegram
http_response_code(200); // Always return 200 to Telegram
if ($response && $http_code == 200) {
    echo $response;
} else {
    echo json_encode([
        "status" => "forwarded",
        "code" => $http_code,
        "environment" => $environment,
        "timestamp" => time(),
        "backend_url" => $backend_url
    ]);
}
?>