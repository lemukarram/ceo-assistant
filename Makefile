.PHONY: up down restart logs ps clean

# Load environment variables if .env exists
ifneq ("$(wildcard .env)","")
    include .env
    export $(shell sed 's/=.*//' .env)
endif

# Default target
all: up

up:
	docker-compose -f plans/docker-compose.yml up -d

down:
	docker-compose -f plans/docker-compose.yml down

restart:
	docker-compose -f plans/docker-compose.yml restart

logs:
	docker-compose -f plans/docker-compose.yml logs -f

ps:
	docker-compose -f plans/docker-compose.yml ps

clean:
	docker-compose -f plans/docker-compose.yml down -v
