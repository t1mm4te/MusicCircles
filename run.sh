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

# Функция: запуск unit-тестов для media_processor
unit_test() {
    echo_info "Running unit tests for media_processor..."
    docker compose run --rm media_processor pytest tests/unit
    check_command "Media processor unit tests"
}

# Функция: запуск unit-тестов для telegram_bot
tb_test() {
    echo_info "Running unit tests for telegram_bot..."
    docker compose run --rm telegram_bot pytest tests/unit
    check_command "Telegram bot unit tests"
}

# Функция: запуск всех тестов
test() {
    unit_test
    tb_test
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
    echo "  unit-test   Run unit tests for media_processor"
    echo "  tb-test     Run unit tests for telegram_bot"
    echo "  test        Run all tests (unit-test + tb-test)"
    echo "  start       Start all services in background"
    echo "  stop        Stop and remove all service containers"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0           # Build, test and start (default)"
    echo "  $0 build     # Only build images"
    echo "  $0 test      # Only run tests"
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
    "unit-test")
        unit_test
        ;;
    "tb-test")
        tb_test
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