import os

orig = "src/tg_time_logger/commands_core.py"
with open(orig) as f:
    lines = f.readlines()

# Extract ranges (1-indexed, inclusive)
to_llm = [
    (1, 47), # imports
    (48, 232),
    (626, 1134),
    (1233, 1513),
]

def in_llm(line_idx):
    for s, e in to_llm:
        if s <= line_idx <= e:
            return True
    return False

llm_lines = []
core_lines = []

for i, line in enumerate(lines, 1):
    if in_llm(i):
        llm_lines.append(line)
        if i <= 47:
            core_lines.append(line) # Keep imports in core too
    else:
        core_lines.append(line)

# Add register_llm_handlers to llm_lines
llm_lines.extend([
    "\n\n",
    "def register_llm_handlers(app: Application) -> None:\n",
    "    app.add_handler(CommandHandler('llm', cmd_llm))\n",
    "    app.add_handler(CallbackQueryHandler(handle_quest_callback, pattern=r'^q2:'))\n",
    "    app.add_handler(CallbackQueryHandler(handle_freeform_callback, pattern=r'^ff:'))\n",
    "    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_form))\n"
])

# Remove those handlers from core_lines
new_core_lines = []
for line in core_lines:
    if "cmd_llm" in line and "CommandHandler" in line: continue
    if "handle_quest_callback" in line and "CallbackQueryHandler" in line: continue
    if "handle_freeform_callback" in line and "CallbackQueryHandler" in line: continue
    if "handle_free_form" in line and "MessageHandler" in line: continue
    new_core_lines.append(line)

with open("src/tg_time_logger/commands_llm.py", "w") as f:
    f.writelines(llm_lines)

with open(orig, "w") as f:
    f.writelines(new_core_lines)

print("Split successful.")
