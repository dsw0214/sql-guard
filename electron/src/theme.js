const PRESET_THEMES = {
    default: { accent: "#43e7ff", accentStrong: "#11c4e6" },
    emerald: { accent: "#34d399", accentStrong: "#10b981" },
    sunset: { accent: "#fb7185", accentStrong: "#f43f5e" },
    amber: { accent: "#fbbf24", accentStrong: "#f59e0b" },
};

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function hexToRgb(hex) {
    const normalized = hex.replace("#", "");
    if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
        return null;
    }

    return {
        r: Number.parseInt(normalized.slice(0, 2), 16),
        g: Number.parseInt(normalized.slice(2, 4), 16),
        b: Number.parseInt(normalized.slice(4, 6), 16),
    };
}

function rgbToHex(r, g, b) {
    const toHex = (v) => clamp(v, 0, 255).toString(16).padStart(2, "0");
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function darken(hex, amount) {
    const rgb = hexToRgb(hex);
    if (!rgb) {
        return "#11c4e6";
    }

    return rgbToHex(
        Math.round(rgb.r * (1 - amount)),
        Math.round(rgb.g * (1 - amount)),
        Math.round(rgb.b * (1 - amount))
    );
}

function normalizeColor(hex, fallback) {
    const value = String(hex || "").trim();
    const normalized = value.startsWith("#") ? value : `#${value}`;
    return hexToRgb(normalized) ? normalized.toLowerCase() : fallback;
}

function resolveTheme(themeMode, customColor) {
    const mode = (PRESET_THEMES[themeMode] || themeMode === "custom") ? themeMode : "default";

    if (mode === "custom") {
        const accent = normalizeColor(customColor, PRESET_THEMES.default.accent);
        return {
            accent,
            accentStrong: darken(accent, 0.18),
        };
    }

    return PRESET_THEMES[mode] || PRESET_THEMES.default;
}

export function applyTheme(themeMode, customColor) {
    const root = document.documentElement;
    const { accent, accentStrong } = resolveTheme(themeMode, customColor);
    const accentRgb = hexToRgb(accent) || hexToRgb(PRESET_THEMES.default.accent);
    const accentStrongRgb = hexToRgb(accentStrong) || hexToRgb(PRESET_THEMES.default.accentStrong);

    root.style.setProperty("--accent", accent);
    root.style.setProperty("--accent-strong", accentStrong);
    root.style.setProperty("--accent-rgb", `${accentRgb.r}, ${accentRgb.g}, ${accentRgb.b}`);
    root.style.setProperty("--accent-strong-rgb", `${accentStrongRgb.r}, ${accentStrongRgb.g}, ${accentStrongRgb.b}`);
    root.style.setProperty("--line", `rgba(${accentRgb.r}, ${accentRgb.g}, ${accentRgb.b}, 0.28)`);
}

export function syncThemeControls(refs) {
    if (!refs.themeMode || !refs.themeColor) {
        return;
    }

    refs.themeColor.disabled = refs.themeMode.value !== "custom";
}

export function normalizeThemeMode(value) {
    const mode = String(value || "").trim();
    if (mode === "custom") {
        return "custom";
    }
    return PRESET_THEMES[mode] ? mode : "default";
}

export function normalizeThemeColor(value) {
    return normalizeColor(value, PRESET_THEMES.default.accent);
}
