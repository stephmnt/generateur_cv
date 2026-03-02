# CV Database Schema (from `cv.yaml`)

Mapping used from YAML:
- `main.experiences.entries` -> `EXPERIENCE`
- `sidebar.formations.entries` -> `FORMATION`
- `sidebar.certifications.entries` -> `CERTIFICATION`
- `sidebar.skills.items` (+ optional normalized skills from `main.digital.categories`) -> `COMPETENCE`

```mermaid
erDiagram
    CV ||--o{ EXPERIENCE : contains
    CV ||--o{ FORMATION : contains
    CV ||--o{ CERTIFICATION : contains
    CV ||--o{ COMPETENCE : defines

    EXPERIENCE ||--o{ EXPERIENCE_COMPETENCE : links
    COMPETENCE ||--o{ EXPERIENCE_COMPETENCE : links

    FORMATION ||--o{ FORMATION_COMPETENCE : links
    COMPETENCE ||--o{ FORMATION_COMPETENCE : links

    CERTIFICATION ||--o{ CERTIFICATION_COMPETENCE : links
    COMPETENCE ||--o{ CERTIFICATION_COMPETENCE : links

    CV {
      int cv_id PK
      string full_name
      string title
      string source_file
    }

    EXPERIENCE {
      int experience_id PK
      int cv_id FK
      string role
      string organization
      text description
      string dates_raw
      int sort_order
    }

    FORMATION {
      int formation_id PK
      int cv_id FK
      string diploma
      string institution
      string dates_raw
      int sort_order
    }

    CERTIFICATION {
      int certification_id PK
      int cv_id FK
      string diploma
      string institution
      string dates_raw
      int sort_order
    }

    COMPETENCE {
      int competence_id PK
      int cv_id FK
      string label
      string source_section
    }

    EXPERIENCE_COMPETENCE {
      int experience_id PK, FK
      int competence_id PK, FK
      string relevance_level
    }

    FORMATION_COMPETENCE {
      int formation_id PK, FK
      int competence_id PK, FK
      string relation_type
    }

    CERTIFICATION_COMPETENCE {
      int certification_id PK, FK
      int competence_id PK, FK
      string relation_type
    }
```

