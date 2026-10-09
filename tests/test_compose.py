from engine.tailoring import compose

SKILLS = {"lang": ["Languages", "C, C++, Python, Java"],
          "embedded": ["Embedded", "microcontroller firmware, hardware bring-up, sensor integration, Linux"],
          "cert": ["Certifications", "5x Salesforce Certified -- Platform Developer I & II"]}


def test_role_name_drops_level_and_team():
    assert compose.role_name("Senior Software Engineer II, Payments (Remote)") == "Software Engineer"
    assert compose.role_name("Embedded Software Engineer - Access Control") == "Embedded Software Engineer"


def test_headline_uses_skill_items_the_jd_mentions_most():
    jd = "<p>Write C++ firmware. Microcontroller firmware, more firmware. Hardware bring-up with C++. Python nice.</p>"
    want = {"c++", "firmware", "microcontroller", "bring-up", "python"}
    h = compose.headline("Firmware Engineer III", jd, want, SKILLS, "fallback")
    assert h.startswith("Firmware Engineer | ")
    assert "microcontroller firmware" in h and "Certified" not in h


def test_headline_falls_back_without_two_terms():
    assert compose.headline("SWE", "nothing relevant", set(), SKILLS, "Lane Headline") == "Lane Headline"


def test_order_skill_line_keeps_items_and_never_touches_credentials():
    line = "C, C++, Python, Java"
    out = compose.order_skill_line(line, {"java", "python"})
    assert out.split(", ")[:2] == ["Python", "Java"] and compose.same_items(out, line)
    assert compose.order_skill_line("5x Certified; Apex, LWC", {"lwc"}) == "5x Certified; Apex, LWC"


def test_summary_keeps_voice_and_never_repeats_the_opener():
    lane = {"summary": "Engineer who builds backends. At Acme I run Kafka services."}
    other = {"summary": "Engineer who likes hardware. Has written C++ firmware for his robots."}
    hits = lambda s: {t for t in ("kafka", "firmware", "c++") if t in s.lower()}
    s = compose.summary("kafka firmware c++", lane, {"a": lane, "b": other}, hits)
    assert s.count("Engineer who builds backends.") == 1
    assert "his robots" not in s  # third-person sentence never joins an "I" summary
