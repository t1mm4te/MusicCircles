#!/bin/bash
# filepath: run.sh

set -e  # Остановить выполнение при любой ошибке

# Функция для вывода сообщений
echo_info() {
    echo "==> $1"
}

# Функция для проверки успешности выполнения команды
check_command() {
    if [ $? -eq 0 ]; then
        echo_info "✅ $1 completed successfully"
    else
        echo_info "❌ $1 failed"
        exit 1
    fi
}

# Функция: сборка Docker-образов для всех сервисов
build() {
    echo_info "Building Docker images..."
    docker compose build
    check_command "Build"
}

# Функция: запуск тестов для database сервиса
database_test() {
    echo_info "Running tests for database..."
    docker compose run --rm database pytest tests/ -v
    check_command "Database tests"
}

# Функция: запуск тестов для audio_receiver
audio_receiver_test() {
    echo_info "Running tests for audio_receiver..."
    docker compose run --rm audio_receiver pytest tests/ -v
    check_command "Audio receiver tests"
}

# Функция: запуск unit-тестов для media_processor
media_processor_test() {
    echo_info "Running tests for media_processor..."
    docker compose run --rm media_processor pytest tests/ -v
    check_command "Media processor tests"
}

# Функция: запуск тестов для telegram_bot
telegram_bot_test() {
    echo_info "Running tests for telegram_bot..."
    docker compose run --rm telegram_bot pytest tests/ -v
    check_command "Telegram bot tests"
}

# Функция: запуск всех тестов
test() {
    database_test
    audio_receiver_test
    media_processor_test
    telegram_bot_test
    echo_info "All tests completed."
}

# Функция: запуск всех сервисов приложения в фоновом режиме
start() {
    echo_info "Starting application services..."
    docker compose up -d
    check_command "Start services"
}

# Функция: остановка и удаление контейнеров всех сервисов приложения
stop() {
    echo_info "Stopping application services..."
    docker compose down
    check_command "Stop services"
}

# Функция: цель по умолчанию (сборка, тестирование, запуск)
all() {
    build
    test
    start
    echo_info "🚀 Application is running! Use './run.sh stop' to stop services."
}

# Функция для отображения справки
help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  all         Build, test and start services (default)"
    echo "  build       Build Docker images for all services"
    echo "  db-test     Run tests for database service"
    echo "  ar-test     Run tests for audio_receiver"
    echo "  mp-test     Run tests for media_processor"
    echo "  tb-test     Run tests for telegram_bot"
    echo "  test        Run all tests"
    echo "  start       Start all services in background"
    echo "  stop        Stop and remove all service containers"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0           # Build, test and start (default)"
    echo "  $0 build     # Only build images"
    echo "  $0 test      # Run all tests"
    echo "  $0 start     # Only start services"
    echo "  $0 stop      # Stop services"
}

# Основная логика скрипта
case "${1:-all}" in
    "all")
        all
        ;;
    "build")
        build
        ;;
    "db-test")
        database_test
        ;;
    "ar-test")
        audio_receiver_test
        ;;
    "mp-test")
        media_processor_test
        ;;
    "tb-test")
        telegram_bot_test
        ;;
    "test")
        test
        ;;
    "start")
        start
        ;;
    "stop")
        stop
        ;;
    "help"|"-h"|"--help")
        help
        ;;
    *)
        echo_info "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac

echo_info "Script completed successfully!"