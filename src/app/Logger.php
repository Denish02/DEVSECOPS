<?php

declare(strict_types=1);

namespace App;

use Monolog\Logger as MonologLogger;
use Monolog\Handler\StreamHandler;

final class Logger
{
    private static ?MonologLogger $instance = null;

    public static function get(): MonologLogger
    {
        if (self::$instance === null) {
            self::$instance = new MonologLogger('cloudmart');
            self::$instance->pushHandler(new StreamHandler('php://stderr'));
        }

        return self::$instance;
    }
}
