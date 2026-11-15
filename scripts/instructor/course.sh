#!/usr/bin/env bash
# Instructor tool: run the course lifecycle on the GitHub organization.
#
#   ./course.sh create-repos              team repos from the template (team.yaml set per team)
#   ./course.sh create-teams              one GitHub team per repo, with write access
#   ./course.sh invite roster.csv         invite students into their team (org invitation by email)
#   ./course.sh codespaces-on roster.csv  the org pays Codespaces for the students in the roster only
#   ./course.sh status                    codespaces, pending invitations, teams
#   ./course.sh stop-codespaces           stop every running codespace in the org (work is kept)
#   ./course.sh end-course                stop codespaces, org Codespaces off, teams read-only, repos archived
#   ./course.sh delete-codespaces         delete every org-billed codespace (unpushed work is lost)
#   ./course.sh offboard roster.csv       remove students from the org (public repos stay readable/forkable)
#
# roster.csv: github_username,team   e.g.  octocat,1
# Needs: gh logged in with scopes repo, workflow, admin:org, codespace
#        gh auth refresh -h github.com -s admin:org,codespace
set -euo pipefail

ORG="${ORG:-majlisofai}"
TEMPLATE="${TEMPLATE:-mlops-course-template}"
TEAMS="${TEAMS:-5}"
PREFIX="${PREFIX:-mlops-team}"
# Dataset per team number; teams can change it later in team.yaml.
dataset_for() { if [ "$1" -le 3 ]; then echo f1; else echo spl; fi; }

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
roster() { grep -vE '^\s*(#|$|github_username)' "$1" | tr -d ' \r'; }
need_roster() { [ -n "${1:-}" ] && [ -f "$1" ] || { echo "usage: $0 $CMD roster.csv" >&2; exit 1; }; }

create_repos() {
  gh api -X PATCH "repos/$ORG/$TEMPLATE" -F is_template=true >/dev/null
  for n in $(seq 1 "$TEAMS"); do
    repo="$PREFIX-$n"; ds=$(dataset_for "$n")
    if gh repo view "$ORG/$repo" >/dev/null 2>&1; then
      say "$ORG/$repo exists"
    else
      say "creating $ORG/$repo from $TEMPLATE ($ds)"
      gh repo create "$ORG/$repo" --public --template "$ORG/$TEMPLATE" \
        --description "MLOps course - team $n workspace (open in Codespaces)" >/dev/null
      for _ in $(seq 1 20); do  # the template copy is asynchronous
        gh api "repos/$ORG/$repo/contents/team.yaml" >/dev/null 2>&1 && break
        sleep 3
      done
      tmp=$(mktemp -d)
      gh repo clone "$ORG/$repo" "$tmp" -- -q
      sed -i.bak -e "s/^team: .*/team: team-$n/" -e "s/^dataset: [a-z0-9]*/dataset: $ds/" "$tmp/team.yaml"
      sed -i.bak "s#$ORG/$TEMPLATE#$ORG/$repo#g" "$tmp/README.md"
      rm -f "$tmp"/*.bak
      git -C "$tmp" commit -qam "Configure team $n ($ds)"
      git -C "$tmp" push -q
      rm -rf "$tmp"
    fi
  done
}

create_teams() {
  for n in $(seq 1 "$TEAMS"); do
    repo="$PREFIX-$n"; team="$PREFIX-$n"
    if ! gh api "orgs/$ORG/teams/$team" >/dev/null 2>&1; then
      say "creating team $team"
      gh api "orgs/$ORG/teams" -f name="$team" -f privacy=closed \
        -f description="MLOps course team $n" >/dev/null
    fi
    gh api -X PUT "orgs/$ORG/teams/$team/repos/$ORG/$repo" -f permission=push >/dev/null
    say "team $team has write access to $ORG/$repo"
  done
}

invite() {
  need_roster "${1:-}"
  roster "$1" | while IFS=, read -r user n; do
    # Adds org members to the team; sends non-members an org invitation that joins them to the team.
    state=$(gh api -X PUT "orgs/$ORG/teams/$PREFIX-$n/memberships/$user" -f role=member --jq .state)
    say "$user -> $PREFIX-$n ($state)"
  done
}

codespaces_on() {
  need_roster "${1:-}"
  users=$(roster "$1" | cut -d, -f1 | jq -R . | jq -sc .)
  gh api -X PUT "orgs/$ORG/codespaces/access" --input - <<<"{\"visibility\":\"selected_members\",\"selected_usernames\":$users}" >/dev/null
  say "org-paid Codespaces enabled for: $(echo "$users" | jq -r 'join(", ")')"
  echo "    Students who had not accepted their invitation yet are skipped - run this again after they join."
}

status() {
  say "codespaces in $ORG"
  gh api --paginate "orgs/$ORG/codespaces" \
    --jq '.codespaces[] | [.owner.login, .repository.name, .state, .machine.name, .last_used_at] | @tsv' | column -t || true
  say "pending invitations"
  gh api --paginate "orgs/$ORG/invitations" --jq '.[] | [.login // .email, .created_at] | @tsv' | column -t || true
  say "teams"
  for n in $(seq 1 "$TEAMS"); do
    printf '  %s: %s\n' "$PREFIX-$n" "$(gh api "orgs/$ORG/teams/$PREFIX-$n/members" --jq '[.[].login] | join(", ")' 2>/dev/null || echo '-')"
  done
}

each_codespace() { # action: stop | delete
  gh api --paginate "orgs/$ORG/codespaces" --jq '.codespaces[] | [.owner.login, .name, .state] | @tsv' |
    while IFS=$'\t' read -r user name state; do
      if [ "$1" = stop ]; then
        [ "$state" = Shutdown ] && continue
        gh api -X POST "orgs/$ORG/members/$user/codespaces/$name/stop" >/dev/null && say "stopped $name ($user)"
      else
        gh api -X DELETE "orgs/$ORG/members/$user/codespaces/$name" >/dev/null && say "deleted $name ($user)"
      fi
    done
}

end_course() {
  each_codespace stop
  gh api -X PUT "orgs/$ORG/codespaces/access" -f visibility=disabled >/dev/null
  say "org-paid Codespaces disabled"
  for n in $(seq 1 "$TEAMS"); do
    gh api -X PUT "orgs/$ORG/teams/$PREFIX-$n/repos/$ORG/$PREFIX-$n" -f permission=pull >/dev/null
    gh repo archive "$ORG/$PREFIX-$n" --yes >/dev/null
    say "$PREFIX-$n: team read-only, repo archived"
  done
  cat <<EOF

Students keep read access to their public repos and can fork them to their own account,
where Codespaces bill their personal account (free monthly quota), not $ORG.
Stopped codespaces still cost storage until deleted: give students a deadline to push
anything left, then run:  $0 delete-codespaces
EOF
}

delete_codespaces() {
  read -r -p "Delete EVERY codespace in $ORG? Unpushed work is lost. Type the org name to confirm: " answer
  [ "$answer" = "$ORG" ] || { echo "aborted"; exit 1; }
  each_codespace delete
}

offboard() {
  need_roster "${1:-}"
  roster "$1" | cut -d, -f1 | while read -r user; do
    gh api -X DELETE "orgs/$ORG/memberships/$user" >/dev/null 2>&1 && say "removed $user from $ORG"
  done
}

CMD="${1:-}"; shift || true
case "$CMD" in
  create-repos) create_repos ;;
  create-teams) create_teams ;;
  invite) invite "$@" ;;
  codespaces-on) codespaces_on "$@" ;;
  status) status ;;
  stop-codespaces) each_codespace stop ;;
  end-course) end_course ;;
  delete-codespaces) delete_codespaces ;;
  offboard) offboard "$@" ;;
  *) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
