-- Shared appearance categories. Extend these expressions for custom app classes.
local families = {
    kitty = "(?i:kitty|agentoo-dropdown|agentoo-clipboard)",
    browser = "(?i:firefox(-bin|-esr|-developeredition|-nightly)?|org.mozilla.firefox|librewolf|floorp|zen(-browser)?|chromium(-browser)?|google-chrome(-stable|-beta|-unstable)?|chrome|brave(-browser)?|com.brave.Browser|microsoft-edge(-stable|-beta|-dev)?|vivaldi(-stable)?|opera)",
}

-- RE2 negative matching excludes the union without unsupported lookarounds.
families.other = "negative:(" .. families.kitty .. "|" .. families.browser .. ")"
return families
