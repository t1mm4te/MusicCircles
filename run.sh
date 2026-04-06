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

# Вспомогательная функция для запуска pytest внутри контейнера
# Аргументы: $1 - имя сервиса, $2 - путь к тестам
run_pytest_in_service() {
    local SERVICE=$1
    local TEST_PATH=${2:-tests/} 
    
    echo_info "Running tests for $SERVICE in $TEST_PATH..."
    docker compose run --rm "$SERVICE" pytest "$TEST_PATH" -v
    check_command "$SERVICE tests ($TEST_PATH)"
}

# Функция: сборка Docker-образов для всех сервисов
build() {
    echo_info "Building Docker images..."
    docker compose build
    check_command "Build"
}

# Функции запуска тестов для конкретных сервисов
database_test() {
    local TEST_PATH=${1:-tests/}  # Берем путь из аргумента
    echo_info "Running tests for database in $TEST_PATH..."
    
    # ПРИНУДИТЕЛЬНО передаем переменную и используем правильный путь
    docker compose run --rm -e DATABASE_PATH=":memory:" database pytest "$TEST_PATH" -v
    check_command "Database tests"
}

audio_receiver_test() {
    run_pytest_in_service "audio_receiver" "$1"
}

media_processor_test() {
    run_pytest_in_service "media_processor" "$1"
}

telegram_bot_test() {
    run_pytest_in_service "telegram_bot" "$1"
}

# Функция: запуск всех тестов (Unit, Integration, E2E) последовательно
test_all() {
    echo_info "Starting full test suite..."
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

# Функция: остановка и удаление контейнеров
stop() {
    echo_info "Stopping application services..."
    docker compose down
    check_command "Stop services"
}

# Цель по умолчанию
all() {
    build
    test_all
    start
    echo_info "🚀 Application is running! Use './run.sh stop' to stop services."
}

# Справка
help() {
    echo "Usage: $0 [COMMAND] [TEST_PATH]"
    echo ""
    echo "Commands:"
    echo "  all             Build, test and start services (default)"
    echo "  build           Build Docker images"
    echo "  db-test [path]  Run tests for database (default: tests/)"
    echo "  ar-test [path]  Run tests for audio_receiver"
    echo "  mp-test [path]  Run tests for media_processor"
    echo "  tb-test [path]  Run tests for telegram_bot"
    echo "  test            Run ALL tests in ALL services"
    echo "  start           Start all services in background"
    echo "  stop            Stop and remove containers"
    echo ""
    echo "Examples:"
    echo "  $0 db-test tests/unit          # Запуск только unit-тестов базы"
    echo "  $0 mp-test tests/integration   # Запуск интеграционных тестов процессора"
    echo "  $0 tb-test tests/e2e           # Запуск E2E тестов бота"
}

# Основная логика обработки аргументов
case "${1:-all}" in
    "all")
        all
        ;;
    "build")
        build
        ;;
    "db-test")
        database_test "$2"
        ;;
    "ar-test")
        audio_receiver_test "$2"
        ;;
    "mp-test")
        media_processor_test "$2"
        ;;
    "tb-test")
        telegram_bot_test "$2"
        ;;
    "test")
        test_all
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
        help
        exit 1
        ;;
esac

echo_info "Script completed successfully!"