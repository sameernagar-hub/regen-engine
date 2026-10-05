// Profile (semantic memory)
CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE;
// (:Person)-[:HAS_FACT]->(:Fact)-[:DEMONSTRATES]->(:Skill)
// (:Fact)-[:AT]->(:Role)-[:AT_ORG]->(:Org)      (:Project)-[:USES]->(:Skill)
// (:Person)-[:PREFERS]->(:Preference {key, value})   e.g. location, sponsorship, level

// World + episodes (episodic memory)
CREATE CONSTRAINT job_key IF NOT EXISTS FOR (j:Job) REQUIRE j.key IS UNIQUE;     // "<ats>:<token>:<id>"
CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE;
// (:Job)-[:AT]->(:Company)   (:Job)-[:REQUIRES]->(:Skill)   (:Job)-[:HAS_CONSTRAINT]->(:Constraint {type:"clearance"|"grad_window"|...})
// (:Job)-[:FOUND_VIA]->(:Source {name})   (:Job)-[:HOSTED_ON]->(:ATS {name})
// (:Application)-[:FOR]->(:Job)   (:Application)-[:USED]->(:ResumeVariant {lane, file})-[:INCLUDES]->(:Fact)
// (:Application)-[:ANSWERED {value}]->(:Question {label})
// (:Application)-[:RESULTED_IN]->(:Outcome {type:"confirmation"|"oa"|"interview"|"rejection"|"offer", at})

// Procedural memory
// (:ATS)-[:HAS_FIELD {label_pattern, preset_key, success_count}]->(:FieldMapping)
