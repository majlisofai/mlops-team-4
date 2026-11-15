# Instructor guide

The course has three phases. During the course, the organization pays for Codespaces, and only for the invited students. After the course, Codespaces are switched off and deleted. Students keep read access to their code and can fork it to run on their own account.

```text
majlisofai/mlops-course-template   (template repo, this one)
 ├── majlisofai/mlops-team-1  ← GitHub team mlops-team-1 (write)   dataset f1
 ├── majlisofai/mlops-team-2  ← mlops-team-2                         f1
 ├── majlisofai/mlops-team-3  ← mlops-team-3                         f1
 ├── majlisofai/mlops-team-4  ← mlops-team-4                         spl
 └── majlisofai/mlops-team-5  ← mlops-team-5                         spl
```

The lifecycle runs through [`scripts/instructor/course.sh`](../scripts/instructor/course.sh). It needs `gh` with admin rights on the organization:

```bash
gh auth refresh -h github.com -s admin:org,codespace
```

## Before the course

1. **Billing (once, in the browser, as the org owner).** The API cannot do this step.
   - *Organization ▸ Settings ▸ Billing and licensing ▸ Payment information*: add a payment method.
   - *Billing ▸ Budgets and alerts*: create a **Codespaces budget** with a hard stop ("stop usage when budget limit is reached"). At the time of writing, a 2-core machine costs about $0.18 per hour plus storage; check the current price. For example, 25 students × 3 days × 8 hours ≈ 600 hours ≈ $110 plus storage.
   - *Settings ▸ Codespaces ▸ General ▸ Codespaces ownership*: choose **Organization ownership**.
2. **Codespaces policies.** Go to *Settings ▸ Codespaces ▸ Policies ▸ Create policy* and apply it to all repositories:
   - Machine types: allow **2-core** only.
   - Maximum idle timeout: **30 minutes**.
   - Maximum codespaces per user: **1** (or 2).
   - Retention period: **7 days**, so a stopped codespace is deleted automatically.
3. **Repos and teams**:
   ```bash
   scripts/instructor/course.sh create-repos
   scripts/instructor/course.sh create-teams
   ```
4. **Invite the students.** Copy `scripts/instructor/roster.example.csv` to `roster.csv` (git-ignored) with one `github_username,team` line per student, then run:
   ```bash
   scripts/instructor/course.sh invite roster.csv
   ```
   Students receive an email and must accept the invitation. Accepting also adds them to their team.
5. **Turn on org-paid Codespaces for the roster only.** Run this after they accept, and run it again for latecomers:
   ```bash
   scripts/instructor/course.sh codespaces-on roster.csv
   ```
6. **The AI agents (Claude in GitHub Actions).** They run in Actions only, on one org API key, with nothing in the students' Codespaces:
   - In the [Anthropic Console](https://console.anthropic.com), create a workspace for the course with a **monthly spend limit**, and an API key in it.
   - Install the Claude GitHub App on the template and the team repos: <https://github.com/apps/claude>, then *Only select repositories*.
   - Store the key as an org secret for the course repos only:
     ```bash
     scripts/instructor/course.sh agents-on
     ```
   Each invocation also has its own cap (`--max-budget-usd`): $3 for `@claude` in `claude.yml`, $2 for the PR review in `claude-review.yml` and $1 for the run report in `pipeline.yml`. The PR review runs once per PR (opened, reopened, ready for review), not on every push. Only users with write access can trigger `@claude`. Without the secret, the agent steps are skipped or fail; the pipeline itself still runs.
7. Test with your own account: open a team repo, then **Code ▸ Codespaces ▸ Create**, run `make pipeline`, and check that the MLflow UI opens from the PORTS tab. Then open an issue in a team repo with `@claude run the pipeline and summarise the result`.

## During the course

```bash
scripts/instructor/course.sh status            # who is running what, pending invitations, team members
scripts/instructor/course.sh stop-codespaces   # end of each day: stop compute, keep everyone's work
```

Watch the cost under *Settings ▸ Billing ▸ Usage* (filter: Codespaces), and the agents' spend in the Anthropic Console (the course workspace).

To ship a fix to every team (a skill, a workflow, the pipeline): change it in the template, push, then run:

```bash
scripts/instructor/course.sh sync .claude CLAUDE.md .github
```

`sync` overwrites those paths in the team repos, so sync only files the teams don't edit, or sync before they start.

## After the course

1. Tell students to **push everything** and give them a deadline.
2. End the course:
   ```bash
   scripts/instructor/course.sh end-course
   ```
   This command stops every codespace, sets org Codespaces access to **disabled** (so nothing new starts at the org's expense), deletes the `ANTHROPIC_API_KEY` org secret (so the agents stop), makes each team read-only on its repo, and archives the team repos. Also revoke the key in the Anthropic Console.
3. After the deadline, delete the stopped codespaces, which still cost storage. The retention policy does this automatically within 7 days, or do it now:
   ```bash
   scripts/instructor/course.sh delete-codespaces
   ```
4. Optional: remove the students from the org.
   ```bash
   scripts/instructor/course.sh offboard roster.csv
   ```
   The repos are public, so students can still read them and **fork** them to their personal account. Codespaces on a fork, or on a public repo opened from their own account, bill the student's personal account, which has a free monthly quota. They do not bill `majlisofai`.

## Next course

Delete or rename the old `mlops-team-*` repos and teams, then run `create-repos` again. To change the data, update `source.ref` in `configs/*.yaml` to a new commit of `mlops-training-dataset`. CI checks that the facts in `configs/*.yaml` still match the data.
