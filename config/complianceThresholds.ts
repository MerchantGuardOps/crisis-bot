// config/complianceThresholds.ts
export const thresholds = {
  vamp: {
    warn_cb_rate: 0.0065,     // 0.65% (warning threshold)
    breach_cb_rate: 0.0100,   // 1.00% (monitoring threshold)
    fine_bands_usd: [5000, 25000, 50000], // illustrative fine bands
  },
  pix: {
    green_max: 0.0030,        // 0.30% (green tier max)
    watch_min: 0.0045,        // 0.45% (watch tier min)
    red_min:   0.0055,        // 0.55% (red tier min)
    reserve_bands: { 
      green: "10%", 
      watch: "15%", 
      red: "20% + 150 bps" 
    },
  },
} as const;