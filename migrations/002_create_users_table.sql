-- proyecto-aegisia/migrations/002_create_users_table.sql

CREATE DATABASE IF NOT EXISTS users;

USE users;

CREATE TABLE IF NOT EXISTS users (
    email VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(255),
    nationality VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,  /* Aumenté el tamaño para hashes seguros */
    PRIMARY KEY (email),
    FULLTEXT INDEX buscador (email, nationality, full_name)  /* Corregí FULLTEXT KEY */
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS api_key (
    email VARCHAR(50) NOT NULL UNIQUE,
    api_key_public VARCHAR(50) NOT NULL,
    api_key_private VARCHAR(50) NOT NULL,  /* Corregí NOT NUL a NOT NULL */
    PRIMARY KEY (email),  /* Corregí PRYMARY KEY */
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE  /* Relación opcional */
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;