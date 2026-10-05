# rewrites one Claude flavoured file from skills/ or agents/ for Codex. install.sh runs it.
# usage: awk -v emit=skill|yaml|role -v skills="next-phase review-ticket ..." -f skill.awk FILE
#   skill  SKILL.md for .agents/skills/<name>/: frontmatter cut to name and a quoted description
#          (a colon inside a plain YAML value breaks a strict parser), $ARGUMENTS and /slash
#          mentions turned into prose and $skill mentions, Claude only commands and files replaced
#   yaml   agents/openai.yaml that goes beside it (display name, short description, default
#          prompt, and the policy that makes the skill explicit only)
#   role   the body of an agents/*.md file without its frontmatter: the loop and the manual
#          review command put it in front of the prompt, because Codex has no --agent
# plain awk only: no regex intervals, no gensub, no match() arrays. bash 3.2, mawk, gawk, BSD awk.

BEGIN {
  n_skills = split(skills, SK, " ")
  WORDCH = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./~-"
  AFTERCH = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_/-"
  fm = 0
  nbody = 0
  used_args = 0
  dropping = 0
  skip_blank = 0
}

function replace_all(s, from, to,    out, i) {
  out = ""
  while ((i = index(s, from)) > 0) {
    out = out substr(s, 1, i - 1) to
    s = substr(s, i + length(from))
  }
  return out s
}

# /next-phase becomes $next-phase, but not inside a path such as skills/next-phase/SKILL.md
function mentions(s,    k, tok, out, rest, i, prev, nxt) {
  for (k = 1; k <= n_skills; k++) {
    tok = "/" SK[k]
    out = ""
    rest = s
    while ((i = index(rest, tok)) > 0) {
      prev = (i > 1) ? substr(rest, i - 1, 1) : substr(out, length(out), 1)
      nxt = substr(rest, i + length(tok), 1)
      if ((prev == "" || index(WORDCH, prev) == 0) && (nxt == "" || index(AFTERCH, nxt) == 0)) {
        out = out substr(rest, 1, i - 1) "$" SK[k]
      } else {
        out = out substr(rest, 1, i - 1 + length(tok))
      }
      rest = substr(rest, i + length(tok))
    }
    s = out rest
  }
  return s
}

# one line of text. sets dropline when the line must disappear.
function conv(s,    i, a, b, ind, args, rules) {
  dropline = 0
  i = index(s, "claude -p \"/review-ticket ")
  if (i > 0) {
    ind = s
    sub(/[^ \t].*$/, "", ind)
    a = index(s, "\"/review-ticket ") + length("\"/review-ticket ")
    args = substr(s, a)
    b = index(args, "\"")
    args = substr(args, 1, b - 1)
    return ind "{ cat .agents/flow-roles/ticket-reviewer.md; echo; echo '$review-ticket " args "'; } | codex exec --sandbox read-only -"
  }
  i = index(s, "Leave out `--agent")
  if (i > 0) {
    if (substr(s, 1, 1) == "(") {
      dropline = 1
      return ""
    }
    s = substr(s, 1, index(s, " Leave out `--agent") - 1)
    if (index(s, "Use the commit you noted in Step 5.") > 0) {
      s = s " This starts a new Codex session, which needs the network and files outside the workspace. If the sandbox blocks it, give the command to the user to run in their own terminal."
    }
    return s
  }
  rules = "(CLAUDE.md, `.claude/rules/`)"
  i = index(s, rules)
  if (i > 0) s = substr(s, 1, i - 1) "(AGENTS.md)" substr(s, i + length(rules))
  if (index(s, "AGENTS.md") == 0) s = replace_all(s, "CLAUDE.md", "AGENTS.md")
  s = replace_all(s, "/clear", "a fresh session")
  if (index(s, "- **Auto**: commit the code, the ticket and the map together.") == 1) {
    s = s " If git refuses to write because the sandbox protects `.git`, leave the changes uncommitted and say so: the loop commits them for you."
  }
  if (index(s, "$ARGUMENTS") > 0) {
    used_args = 1
    s = replace_all(s, "$ARGUMENTS", "<arguments>")
  }
  return mentions(s)
}

function yaml_quote(s) {
  s = replace_all(s, "\\", "\\\\")
  s = replace_all(s, "\"", "\\\"")
  return "\"" s "\""
}

function trim(s) {
  sub(/^[ \t]+/, "", s)
  sub(/[ \t\r]+$/, "", s)
  return s
}

FNR == 1 && $0 == "---" { fm = 1; next }

fm == 1 {
  if ($0 == "---") { fm = 2; next }
  if (substr($0, 1, 1) == " " || substr($0, 1, 1) == "\t") {
    if (!dropping) head[++nhead] = $0
    next
  }
  dropping = 0
  if (index($0, "name:") == 1) { name = trim(substr($0, 6)); head[++nhead] = $0; next }
  if (index($0, "description:") == 1) { desc = trim(substr($0, 13)); head[++nhead] = "description: " yaml_quote(conv(desc)); next }
  if (index($0, "argument-hint:") == 1) { hint = trim(substr($0, 15)); dropping = 1; next }
  if (index($0, "disable-model-invocation:") == 1) { explicit = (trim(substr($0, 26)) == "true"); dropping = 1; next }
  head[++nhead] = $0
  next
}

{
  line = conv($0)
  if (dropline) { skip_blank = 1; next }
  if (skip_blank && line == "") { skip_blank = 0; next }
  skip_blank = 0
  body[++nbody] = line
}

END {
  if (emit == "role") {
    first = 1
    for (k = 1; k <= nbody; k++) {
      if (first && body[k] == "") continue
      first = 0
      print body[k]
    }
  } else if (emit == "yaml") {
    sd = conv(desc)
    i = index(sd, ". ")
    if (i > 0) sd = substr(sd, 1, i - 1)
    sub(/\.$/, "", sd)
    if (length(sd) > 120) {
      sd = substr(sd, 1, 120)
      while (length(sd) > 0 && substr(sd, length(sd), 1) != " ") sd = substr(sd, 1, length(sd) - 1)
      sd = trim(sd)
    }
    h = hint
    if (substr(h, 1, 1) == "\"" && substr(h, length(h), 1) == "\"") h = substr(h, 2, length(h) - 2)
    print "interface:"
    print "  display_name: " yaml_quote(name)
    print "  short_description: " yaml_quote(sd)
    print "  default_prompt: " yaml_quote("Use $" name (h != "" ? " " h : ""))
    if (explicit) {
      print "policy:"
      print "  allow_implicit_invocation: false"
    }
  } else {
    print "---"
    for (k = 1; k <= nhead; k++) print head[k]
    print "---"
    print ""
    if (used_args) {
      print "`<arguments>` below stands for the text the user typed after `$" name "`."
      print ""
    }
    first = 1
    for (k = 1; k <= nbody; k++) {
      if (first && body[k] == "") continue
      first = 0
      print body[k]
    }
  }
}
