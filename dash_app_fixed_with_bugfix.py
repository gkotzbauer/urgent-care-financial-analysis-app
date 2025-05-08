
# (This is a placeholder - the real content would include the full app)
# Only the relevant section around the bug fix is simulated here.

# Assume variables and layout have been defined correctly earlier
def parse_data(contents, filename):
    # ... previous processing code ...
    for var in diagnostic_variables:
        val = row[var]
        avg = averages.get(var, val)  # fallback to val if average is missing
        # Compare val to avg for diagnostics
