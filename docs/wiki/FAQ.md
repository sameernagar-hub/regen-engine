# FAQ

**Does it use an LLM to write answers?**
No. Resumes and drafted answers are assembled from the Fact Bank. That's what makes "nothing invented" checkable.

**Will it lie on a form to get through?**
No. Legal answers come only from the presets, anything unknown goes to you, and an airbag stops a submission whose
legal answers drift from the presets.

**Does it solve CAPTCHAs?**
No. They're handed to you with the form filled.

**Why only Greenhouse, Ashby, Lever and Workable?**
They publish public job APIs and have consistent forms. Workday and iCIMS need accounts; adapters are planned with the
account created by you.

**How many applications a day?**
The design target is 10+ verified submissions a day with a daily cap of 25 and 3 per company. The scheduler roughly
doubles throughput; bot flags and email codes are the usual limits.

**Where is my data?**
On your machine: `profile/` and `workspace/`, both git-ignored. CI blocks commits that would leak personal data.

**Can I see what it sent?**
Yes: the confirmation screenshot, every question and answer, the facts each resume used, and every drafted answer.

**Does it run on its own?**
Not since v0.8. You start it; `workspace/STOP` stops it.
