/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-11.4.3-MariaDB, for Win64 (AMD64)
--
-- Host: localhost    Database: topeducation
-- ------------------------------------------------------
-- Server version	11.4.3-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Table structure for table `universidades`
--

DROP TABLE IF EXISTS `universidades`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `universidades` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(500) NOT NULL,
  `university_region_id` bigint(20) DEFAULT NULL,
  `university_image` varchar(300) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `Universidades_university_region_id_78f519cf_fk_Regiones_id` (`university_region_id`),
  CONSTRAINT `Universidades_university_region_id_78f519cf_fk_Regiones_id` FOREIGN KEY (`university_region_id`) REFERENCES `regiones` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=44 DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `universidades`
--

LOCK TABLES `universidades` WRITE;
/*!40000 ALTER TABLE `universidades` DISABLE KEYS */;
INSERT INTO `universidades` VALUES
(1,'Macquarie University',NULL,NULL),
(2,'IE Business School',NULL,NULL),
(3,'Universidad Autónoma de Barcelona',NULL,NULL),
(4,'Universidad Carlos III de Madrid',NULL,NULL),
(5,'Universidad Nacional de Colombia',NULL,NULL),
(6,'University of New Mexico',NULL,NULL),
(7,'University of Michigan',NULL,NULL),
(8,'University of Virginia',NULL,NULL),
(9,'Harvard university',NULL,NULL),
(10,'Yale University',NULL,NULL),
(11,'Universidad Austral',NULL,NULL),
(19,'Universidad de Palermo',NULL,NULL),
(20,'Pontificia Universidad Catolica de Chile',NULL,NULL),
(21,'SAE-México',NULL,NULL),
(22,'Universidad Anáhuac',NULL,NULL),
(23,'Berklee College of Music',NULL,NULL),
(24,'Yad Vashem',NULL,NULL),
(25,'Universidad de los Andes',NULL,NULL),
(26,'UNAM',NULL,NULL),
(28,'Universitat de Barcelona',NULL,NULL),
(29,'Pontificia Universidad Catolica de Peru',NULL,NULL),
(30,'Duke University',NULL,NULL),
(31,'California Institute of Arts',NULL,NULL),
(32,'Wesleyan University',NULL,NULL),
(33,'University of Colorado Boulder',NULL,NULL),
(34,'Northwestern University',NULL,NULL),
(35,'The University of North Carolina at Chapel Hill',NULL,NULL),
(36,'University of California, Irvine',NULL,NULL),
(37,'Tecnológico de Monterrey',NULL,NULL),
(38,'University of Illinois Urbana-Champaign',NULL,NULL),
(39,'Museum of Modern Art',NULL,NULL),
(40,'Parsons School of Design, The New School',NULL,NULL),
(41,'The Chinese University of Hong Kong',NULL,NULL),
(42,'University of Cape Town',NULL,NULL),
(43,'IESE Business School',NULL,NULL);
/*!40000 ALTER TABLE `universidades` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2024-10-31 10:49:23
