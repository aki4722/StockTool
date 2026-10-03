-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: stocktool_bbs
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `bbs_rankings`
--

DROP TABLE IF EXISTS `bbs_rankings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bbs_rankings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL,
  `scrape_time` time NOT NULL,
  `symbol` varchar(20) NOT NULL,
  `company_name` varchar(255) DEFAULT NULL,
  `post_count` int DEFAULT NULL,
  `status` enum('new','existing','dropped') DEFAULT NULL,
  `price` decimal(12,2) DEFAULT NULL,
  `change` decimal(12,2) DEFAULT NULL,
  `change_percent` decimal(8,4) DEFAULT NULL,
  `per` decimal(8,2) DEFAULT NULL,
  `pbr` decimal(8,2) DEFAULT NULL,
  `dividend_yield` decimal(8,2) DEFAULT NULL,
  `equity_ratio` decimal(8,2) DEFAULT NULL,
  `valuation_label` enum('undervalued','neutral','overvalued') DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_date_time_symbol` (`date`,`scrape_time`,`symbol`),
  KEY `idx_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bbs_posts`
--

DROP TABLE IF EXISTS `bbs_posts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bbs_posts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ranking_id` int DEFAULT NULL,
  `symbol` varchar(20) DEFAULT NULL,
  `post_content` text,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_symbol` (`symbol`),
  KEY `fk_ranking` (`ranking_id`),
  CONSTRAINT `fk_ranking` FOREIGN KEY (`ranking_id`) REFERENCES `bbs_rankings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bbs_sentiment`
--

DROP TABLE IF EXISTS `bbs_sentiment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bbs_sentiment` (
  `id` int NOT NULL AUTO_INCREMENT,
  `symbol` varchar(20) NOT NULL,
  `date` date NOT NULL,
  `scrape_time` time NOT NULL,
  `sentiment_score` float DEFAULT NULL,
  `key_topics` text,
  `risk_level` enum('low','medium','high') DEFAULT NULL,
  `analyzed_at` datetime DEFAULT NULL,
  `price` decimal(12,2) DEFAULT NULL,
  `change` decimal(12,2) DEFAULT NULL,
  `change_percent` decimal(8,4) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_date_time_symbol` (`date`,`scrape_time`,`symbol`),
  KEY `idx_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `margin_tracking`
--

DROP TABLE IF EXISTS `margin_tracking`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `margin_tracking` (
  `id` int NOT NULL AUTO_INCREMENT,
  `symbol` varchar(20) NOT NULL,
  `company_name` varchar(255) DEFAULT NULL,
  `added_date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `symbol` (`symbol`),
  KEY `idx_symbol` (`symbol`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `margin_positions`
--

DROP TABLE IF EXISTS `margin_positions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `margin_positions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `symbol` varchar(20) NOT NULL,
  `date` date NOT NULL,
  `long_position` int DEFAULT NULL,
  `short_position` int DEFAULT NULL,
  `margin_ratio` decimal(8,2) DEFAULT NULL,
  `weekly_change_long` int DEFAULT NULL,
  `weekly_change_short` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_symbol_date` (`symbol`,`date`),
  CONSTRAINT `margin_positions_ibfk_1` FOREIGN KEY (`symbol`) REFERENCES `margin_tracking` (`symbol`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed
