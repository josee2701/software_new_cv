"""Seed data: technology catalog (~150 entries) and a realistic example resume (Spanish)."""

from __future__ import annotations

# (canonical, category). category ∈ language | framework | db | cloud | tool
TECHNOLOGIES: list[tuple[str, str]] = [
    # languages
    ("Python", "language"),
    ("Go", "language"),
    ("Java", "language"),
    ("Kotlin", "language"),
    ("JavaScript", "language"),
    ("TypeScript", "language"),
    ("C", "language"),
    ("C++", "language"),
    ("C#", "language"),
    ("Rust", "language"),
    ("Ruby", "language"),
    ("PHP", "language"),
    ("Scala", "language"),
    ("Swift", "language"),
    ("Dart", "language"),
    ("Elixir", "language"),
    ("R", "language"),
    ("SQL", "language"),
    ("Bash", "language"),
    ("PowerShell", "language"),
    ("HTML", "language"),
    ("CSS", "language"),
    ("Lua", "language"),
    ("Clojure", "language"),
    ("Haskell", "language"),
    ("Perl", "language"),
    ("Objective-C", "language"),
    ("Solidity", "language"),
    ("COBOL", "language"),
    ("MATLAB", "language"),
    # frameworks / libraries
    ("FastAPI", "framework"),
    ("Django", "framework"),
    ("Django REST Framework", "framework"),
    ("Flask", "framework"),
    ("Celery", "framework"),
    ("SQLAlchemy", "framework"),
    ("Pydantic", "framework"),
    ("pandas", "framework"),
    ("NumPy", "framework"),
    ("scikit-learn", "framework"),
    ("PyTorch", "framework"),
    ("TensorFlow", "framework"),
    ("Spring Boot", "framework"),
    ("Spring", "framework"),
    ("Hibernate", "framework"),
    ("Quarkus", "framework"),
    ("Node.js", "framework"),
    ("Express", "framework"),
    ("NestJS", "framework"),
    ("React", "framework"),
    ("Next.js", "framework"),
    ("Angular", "framework"),
    ("Vue.js", "framework"),
    ("Svelte", "framework"),
    ("Ruby on Rails", "framework"),
    ("Laravel", "framework"),
    ("Symfony", "framework"),
    (".NET", "framework"),
    ("ASP.NET Core", "framework"),
    ("Entity Framework", "framework"),
    ("Gin", "framework"),
    ("Echo", "framework"),
    ("gRPC", "framework"),
    ("GraphQL", "framework"),
    ("Phoenix", "framework"),
    ("Flutter", "framework"),
    ("React Native", "framework"),
    ("Tailwind CSS", "framework"),
    ("Bootstrap", "framework"),
    ("jQuery", "framework"),
    ("HTMX", "framework"),
    ("Apache Spark", "framework"),
    ("Apache Airflow", "framework"),
    ("dbt", "framework"),
    ("LangChain", "framework"),
    ("OpenAPI", "framework"),
    ("Jest", "framework"),
    ("pytest", "framework"),
    ("JUnit", "framework"),
    ("Playwright", "framework"),
    ("Selenium", "framework"),
    ("Cypress", "framework"),
    # databases / messaging
    ("PostgreSQL", "db"),
    ("MySQL", "db"),
    ("MariaDB", "db"),
    ("SQLite", "db"),
    ("Oracle Database", "db"),
    ("SQL Server", "db"),
    ("MongoDB", "db"),
    ("Redis", "db"),
    ("Elasticsearch", "db"),
    ("OpenSearch", "db"),
    ("Cassandra", "db"),
    ("DynamoDB", "db"),
    ("Firestore", "db"),
    ("Neo4j", "db"),
    ("ClickHouse", "db"),
    ("Snowflake", "db"),
    ("BigQuery", "db"),
    ("Amazon Redshift", "db"),
    ("TimescaleDB", "db"),
    ("CockroachDB", "db"),
    ("Kafka", "db"),
    ("RabbitMQ", "db"),
    ("Amazon SQS", "db"),
    ("Google Pub/Sub", "db"),
    ("Memcached", "db"),
    # cloud
    ("AWS", "cloud"),
    ("Amazon EC2", "cloud"),
    ("Amazon S3", "cloud"),
    ("AWS Lambda", "cloud"),
    ("Amazon ECS", "cloud"),
    ("Amazon EKS", "cloud"),
    ("Amazon RDS", "cloud"),
    ("Amazon CloudWatch", "cloud"),
    ("AWS CloudFormation", "cloud"),
    ("Google Cloud", "cloud"),
    ("Google Kubernetes Engine", "cloud"),
    ("Cloud Run", "cloud"),
    ("Microsoft Azure", "cloud"),
    ("Azure DevOps", "cloud"),
    ("Azure Functions", "cloud"),
    ("Heroku", "cloud"),
    ("DigitalOcean", "cloud"),
    ("Vercel", "cloud"),
    ("Netlify", "cloud"),
    ("Cloudflare", "cloud"),
    ("Firebase", "cloud"),
    ("Oracle Cloud", "cloud"),
    # tools / devops / practices
    ("Docker", "tool"),
    ("Kubernetes", "tool"),
    ("Helm", "tool"),
    ("Terraform", "tool"),
    ("Ansible", "tool"),
    ("Pulumi", "tool"),
    ("Git", "tool"),
    ("GitHub", "tool"),
    ("GitHub Actions", "tool"),
    ("GitLab CI", "tool"),
    ("Jenkins", "tool"),
    ("CircleCI", "tool"),
    ("Argo CD", "tool"),
    ("Prometheus", "tool"),
    ("Grafana", "tool"),
    ("Datadog", "tool"),
    ("New Relic", "tool"),
    ("Sentry", "tool"),
    ("OpenTelemetry", "tool"),
    ("ELK Stack", "tool"),
    ("Nginx", "tool"),
    ("Apache HTTP Server", "tool"),
    ("Linux", "tool"),
    ("Jira", "tool"),
    ("Confluence", "tool"),
    ("Postman", "tool"),
    ("SonarQube", "tool"),
    ("Keycloak", "tool"),
    ("OAuth 2.0", "tool"),
    ("REST", "tool"),
    ("SOAP", "tool"),
    ("Microservicios", "tool"),
    ("Scrum", "tool"),
    ("Kanban", "tool"),
    ("TDD", "tool"),
    ("CI/CD", "tool"),
    ("Figma", "tool"),
    ("Power BI", "tool"),
    ("Tableau", "tool"),
    ("Excel", "tool"),
]

# Aliases (name, canonical): same canonical, found by get_or_create normalization.
ALIASES: list[tuple[str, str]] = [
    ("postgres", "PostgreSQL"),
    ("psql", "PostgreSQL"),
    ("golang", "Go"),
    ("js", "JavaScript"),
    ("ts", "TypeScript"),
    ("k8s", "Kubernetes"),
    ("node", "Node.js"),
    ("nodejs", "Node.js"),
    ("reactjs", "React"),
    ("vue", "Vue.js"),
    ("amazon web services", "AWS"),
    ("gcp", "Google Cloud"),
    ("azure", "Microsoft Azure"),
    ("sklearn", "scikit-learn"),
    ("drf", "Django REST Framework"),
    ("apache kafka", "Kafka"),
    ("mssql", "SQL Server"),
    ("elastic", "Elasticsearch"),
    ("gh actions", "GitHub Actions"),
    ("dotnet", ".NET"),
]

EXAMPLE_RESUME_NAME = "Ejemplo — Backend"

EXAMPLE_BASICS: dict[str, str] = {
    "full_name": "Andrés Felipe Rojas Martínez",
    "headline": "Ingeniero de Sistemas · Backend Python y Go",
    "email": "andres.rojas@example.com",
    "phone": "300 123 4567",
    "city": "Bogotá",
    "region": "Cundinamarca",
    "country": "CO",
    "summary": (
        "Ingeniero de sistemas con 8 años de experiencia diseñando y operando servicios backend "
        "en Python y Go para banca y comercio electrónico. Especializado en APIs de alto tráfico, "
        "arquitectura orientada a eventos, PostgreSQL y AWS. Ha liderado migraciones de monolitos "
        "a microservicios, reducido costos de infraestructura y mejorado la observabilidad de "
        "plataformas críticas de pagos. Enfoque en calidad, pruebas automatizadas y mentoría."
    ),
}

EXAMPLE_LINKS: list[dict[str, str]] = [
    {
        "kind": "linkedin",
        "label": "LinkedIn",
        "url": "https://www.linkedin.com/in/andres-rojas-dev",
    },
    {"kind": "github", "label": "GitHub", "url": "https://github.com/andresrojas-dev"},
]

# Each experience: fields + achievements [(text, metric_value)] + technologies.
EXAMPLE_EXPERIENCES: list[dict[str, object]] = [
    {
        "company": "Banco Andino Digital",
        "role": "Ingeniero Backend Senior",
        "employment_type": "full-time",
        "city": "Bogotá",
        "country": "CO",
        "remote": True,
        "start_date": "2022-03",
        "is_current": True,
        "description": "Equipo de plataforma de pagos digitales (12 personas).",
        "achievements": [
            (
                "Lideré la migración del motor de pagos de un monolito Java a 9 microservicios en "
                "Python y Go, reduciendo la latencia p95 de 820 ms a 190 ms.",
                "-77% latencia",
            ),
            (
                "Diseñé un pipeline de eventos con Kafka que procesa 4,5 millones de transacciones "
                "diarias con 99,98% de disponibilidad.",
                "4,5 M/día",
            ),
            (
                "Reduje 32% el costo mensual de AWS optimizando instancias, "
                "reservas y políticas de "
                "autoescalado en EKS.",
                "32%",
            ),
            (
                "Implementé trazabilidad distribuida con OpenTelemetry, bajando el tiempo medio de "
                "resolución de incidentes de 3 h a 40 min.",
                "-78% MTTR",
            ),
            (
                "Mentoricé a 4 desarrolladores junior; 2 fueron promovidos a "
                "semi-senior en menos de "
                "12 meses.",
                "4 personas",
            ),
        ],
        "technologies": ["Python", "Go", "FastAPI", "PostgreSQL", "Kafka", "AWS", "Kubernetes"],
    },
    {
        "company": "Mercado Ágil S.A.S.",
        "role": "Desarrollador Backend",
        "employment_type": "full-time",
        "city": "Bogotá",
        "country": "CO",
        "remote": False,
        "start_date": "2019-06",
        "end_date": "2022-02",
        "is_current": False,
        "achievements": [
            (
                "Desarrollé la API de catálogo y checkout en Django REST "
                "Framework para 1,2 millones "
                "de usuarios activos mensuales.",
                "1,2 M usuarios",
            ),
            (
                "Aumenté 18% la conversión del checkout eliminando 3 pasos y cacheando precios con "
                "Redis.",
                "18%",
            ),
            (
                "Automaticé la conciliación de pedidos con Celery, ahorrando 60 horas de trabajo "
                "manual al mes.",
                "60 h/mes",
            ),
            (
                "Elevé la cobertura de pruebas de 35% a 82% e introduje CI/CD con GitHub Actions.",
                "82%",
            ),
        ],
        "technologies": ["Python", "Django", "PostgreSQL", "Redis", "Celery", "Docker"],
    },
    {
        "company": "Soluciones TIC Ltda.",
        "role": "Desarrollador de Software",
        "employment_type": "contractor",
        "city": "Medellín",
        "country": "CO",
        "remote": False,
        "start_date": "2017-01",
        "end_date": "2019-05",
        "is_current": False,
        "achievements": [
            (
                "Construí 6 integraciones REST y SOAP entre el ERP y la facturación electrónica de "
                "la DIAN para 40 clientes.",
                "6 integraciones",
            ),
            (
                "Optimicé consultas SQL críticas, reduciendo la generación de reportes de 15 min a "
                "90 segundos.",
                "-90% tiempo",
            ),
            (
                "Levanté requisitos con 5 clientes de salud y logística y "
                "los convertí en historias "
                "de usuario priorizadas.",
                None,
            ),
        ],
        "technologies": ["Python", "Flask", "MySQL", "JavaScript"],
    },
]

EXAMPLE_EDUCATION: list[dict[str, object]] = [
    {
        "institution": "Universidad de los Andes",
        "degree": "Especialización en Arquitectura de Software",
        "level": "specialization",
        "city": "Bogotá",
        "start_date": "2020-02",
        "end_date": "2021-06",
    },
    {
        "institution": "Universidad Nacional de Colombia",
        "degree": "Ingeniería de Sistemas y Computación",
        "level": "bachelor",
        "city": "Bogotá",
        "start_date": "2011-02",
        "end_date": "2016-12",
        "gpa": "4,2 / 5,0",
    },
]

# (category, [(skill, level, years)])
EXAMPLE_SKILLS: list[tuple[str, list[tuple[str, str, int]]]] = [
    (
        "Lenguajes",
        [
            ("Python", "expert", 8),
            ("Go", "advanced", 3),
            ("SQL", "advanced", 8),
            ("TypeScript", "intermediate", 2),
        ],
    ),
    (
        "Frameworks y datos",
        [
            ("FastAPI", "expert", 4),
            ("Django", "advanced", 5),
            ("PostgreSQL", "advanced", 7),
            ("Redis", "advanced", 5),
            ("Kafka", "intermediate", 3),
        ],
    ),
    (
        "Cloud y DevOps",
        [
            ("AWS", "advanced", 4),
            ("Docker", "advanced", 6),
            ("Kubernetes", "intermediate", 3),
            ("Terraform", "intermediate", 2),
            ("GitHub Actions", "advanced", 4),
        ],
    ),
]

EXAMPLE_PROJECTS: list[dict[str, object]] = [
    {
        "name": "pagos-sandbox",
        "role": "Autor y mantenedor",
        "description": (
            "Simulador open source de pasarelas de pago latinoamericanas (PSE, Nequi, tarjetas) "
            "para pruebas de integración; 350 estrellas en GitHub y usado por 3 fintech."
        ),
        "url": "https://github.com/andresrojas-dev/pagos-sandbox",
        "start_date": "2023-01",
        "end_date": "2024-08",
        "technologies": ["Go", "Docker", "OpenAPI"],
    },
    {
        "name": "Aire Bogotá",
        "role": "Colaborador",
        "description": (
            "Plataforma ciudadana que agrega datos de 40 sensores de calidad del aire y publica "
            "alertas por Telegram a más de 3.000 suscriptores."
        ),
        "start_date": "2021-03",
        "end_date": "2021-11",
        "technologies": ["Python", "FastAPI", "TimescaleDB"],
    },
]

EXAMPLE_CERTIFICATIONS: list[dict[str, object]] = [
    {
        "name": "AWS Certified Solutions Architect – Associate",
        "issuer": "Amazon Web Services",
        "issue_date": "2024-05",
        "expiry_date": "2027-05",
        "credential_id": "AWS-SAA-8F3K2L",
    },
    {
        "name": "Certified Kubernetes Application Developer (CKAD)",
        "issuer": "The Linux Foundation",
        "issue_date": "2025-02",
        "expiry_date": "2027-02",
        "url": "https://www.credly.com/badges/ckad-andresrojas",
    },
]

EXAMPLE_LANGUAGES: list[tuple[str, str]] = [("Español", "native"), ("Inglés", "C1")]
