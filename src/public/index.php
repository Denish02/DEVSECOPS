<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';

use App\Logger;

Logger::get()->info('Home page requested', ['ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown']);

$name = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['name'])) {
    // Trim and cap length; output is escaped below, never echoed raw.
    $name = substr(trim((string) $_POST['name']), 0, 80);
}

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CloudMart</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <h1>CloudMart Sample App</h1>
    <p>This is a minimal application used to demonstrate the CloudMart DevSecOps pipeline.</p>

    <form method="post" action="/index.php">
        <label for="name">Your name:</label>
        <input type="text" id="name" name="name" maxlength="80">
        <button type="submit">Greet me</button>
    </form>

    <?php if ($name !== ''): ?>
        <p>Hello, <?= htmlspecialchars($name, ENT_QUOTES, 'UTF-8') ?>!</p>
    <?php endif; ?>

    <p><a href="/about.php">About</a></p>
</body>
</html>
