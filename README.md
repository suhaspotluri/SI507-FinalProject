# SI507-FinalProject
To run the code yourself you will need to connect to the database as the code’s functionality is dependent on the database. You can create your own using the provided schema if you want. The application has many Python dependencies. You will need the following packages: flask, config, mysql_connector, flask_limiter, requests_cache, folium, and openrouteservice. You can run pip install -r requirements.txt. 
To run on your localhost just run app.py. 
I also have the app running on an AWS EC2 instance for testing: http://54.202.81.128/ username: test, password: test1.

I use two different APIs (openrouteservice.org, openweathermap.org). The API keys will need to be entered into a file called secrets.py in the root directory of the app (see secretsEx.py). The free tier API keys are sufficient. The MySQL database credentials will also need to be entered here. 
database='tripweather'

Schema:

CREATE TABLE `segments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `start` varchar(100) DEFAULT NULL,
  `sname` varchar(45) DEFAULT NULL,
  `tid` int DEFAULT NULL,
  `duration` int DEFAULT NULL,
  `distance` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=40 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `trips` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tname` varchar(450) NOT NULL,
  `sdate` datetime NOT NULL,
  `uid` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL,
  `password` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=65 DEFAULT CHARSET=latin1;


