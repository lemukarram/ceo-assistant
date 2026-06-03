.PHONY: up down restart logs ps clean

# Load environment variables if .env exists
ifneq ("$(wildcard .env)","")
    include .env
    export $(shell sed 's/=.*//' .env)
endif

# Default target
all: up

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

ps:
	docker-compose ps

clean:
	docker-compose down -v
