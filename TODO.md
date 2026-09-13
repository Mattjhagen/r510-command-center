# R510 Command Center TODO

## Priority Tasks

### 🔴 HIGH PRIORITY: Camera Integration
**BLOCKER:** Traffic camera sites block automated access (403 Forbidden)

**Action Required:**
1. Manually visit https://trafficvision.live/?state=Nebraska&search=Omaha in browser
2. Open browser DevTools (F12) and inspect camera elements
3. Find actual image URLs (likely .jpg or .m3u8 streams)
4. Extract 6-10 Omaha camera URLs with locations
5. Hard-code URLs into dashboard

**Sites Checked:**
- ❌ trafficvision.live - 403 Forbidden on automated requests
- ❌ 511.nebraska.gov - No direct camera API found
- ❌ cityofomaha.org - 403 Forbidden
- ❌ opencctv.org - No working Omaha feeds

**Alternative Approach:**
- Use YouTube live streams of Omaha traffic (if available)
- Check local news station live camera pages (KETV, WOWT, KMTV)
- Contact Nebraska DOT for API access

### Aircraft Data Enhancement
- [ ] Investigate FlightRadar24 receiver API
  - Device detected at 192.168.0.4 (17 aircraft)
  - Has web interface but no standard JSON endpoint
  - May need custom scraper or reverse engineer their API
- [ ] Alternative: Keep using OpenSky Network (currently working with 9 aircraft)

### Future Features
- [ ] Real crime data integration (SpotCrime API or local CAD feed)
- [ ] SHAGGOTH-A1 status integration
- [ ] Historical crime heatmap overlay
- [ ] Aircraft trail visualization
- [ ] Emergency squawk alert notifications
- [ ] Weather radar overlay

## Completed
- [x] OpenStreetMap integration
- [x] OpenSky Network aircraft data
- [x] Crime-focused dashboard with detail panel
- [x] Pulsating red dots for emergency squawks
- [x] Color-coded crime severity system
- [x] Auto-start on boot for all services
- [x] Chromium kiosk mode on R510 monitor
