# iPhone setup ▲

You need: your app link (`https://<you>.github.io/<repo>/`) and your passcode.

## 1. Home-screen app (2 min)
1. Open your app link in **Safari**.
2. Tap **Share** (□↑) → **Add to Home Screen** → **Add**.
3. Open **Dead Ahead** from your home screen, enter your passcode, and keep "Remember on this device" ticked.

## 2. Scriptable (powers the widget + wallpaper)
1. Install **[Scriptable](https://apps.apple.com/app/scriptable/id1405459188)** (free).
2. In Safari, open
   `https://raw.githubusercontent.com/<you>/<repo>/main/scriptable/Dead%20Ahead.js`
   → select all → **Copy**.
3. In Scriptable tap **+**, paste, then tap the title at the top and name it **Dead Ahead**. Tap **Done**.
4. Tap the script to run it → **Set up** → paste your app link + passcode → **Save**.
   You should see **✓ Connected**.
   *(Try **Preview wallpaper** and **Preview lock-screen widget** from the same menu.)*

## 3. Lock-screen widget: urgent work
1. Lock your phone, then press and hold the lock screen → **Customize** → **Lock Screen**.
2. Tap the widget area under the clock → find **Scriptable** → pick the **wide rectangle** → tap **Done**.
3. Tap the new widget → **Script: Dead Ahead**.
4. Tap ✕, then **Done**.

It shows how many things are due in the next 7 days, how many are late, and the next two items. It refreshes itself
through the day (iOS decides exactly when, usually every 15–60 min).

> Tip: there's also a home-screen widget (small/medium/large). Add a Scriptable widget, then pick **Dead Ahead**.

## 4. Daily wallpaper: the whole week
**Make the shortcut**
1. Open **Shortcuts** → **+** → name it **Dead Ahead Wallpaper**.
2. Add action **Run Script** (Scriptable) → Script: **Dead Ahead** → tap *Parameter* and type `wallpaper`.
3. Add action **Base64 Encode**, tap *Encode* and change it to **Decode**. (Scriptable hands the picture over as
   text; this turns it back into an image.)
4. Add action **Set Wallpaper Photo** → set it to **Lock Screen**. Tap the arrow and turn **off** *Show Preview*
   and *Crop to Subject*.
5. Tap ▶︎ once to test. Your lock screen should now show your week.

**Run it every morning**
1. Shortcuts → **Automation** → **+** → **Time of Day** → `6:00 AM`, **Daily**.
2. Choose **Run Immediately** (not "Run After Confirmation").
3. **Next** → pick **Dead Ahead Wallpaper** → **Done**.

> If you have several lock screens, *Set Wallpaper Photo* updates the one that's currently active.
> Add a second automation (e.g. 2:00 PM) for an afternoon refresh.

**Use your own photo behind the list (optional):** save a photo in **Files → iCloud Drive → Scriptable** named
`dead-ahead-background.jpg`. Dead Ahead dims it so the text stays readable.

## Troubleshooting
| Problem | Fix |
|---|---|
| "Wrong passcode" | It must match the `DEADAHEAD_PASSCODE` secret exactly. Run the script → *Change site / passcode*. |
| Widget says "open Scriptable to set up" | Run the script in Scriptable once (step 2.4). |
| App says "not refreshing" | GitHub paused the schedule. On GitHub: **Actions → Update deadlines → Enable workflow**. |
| Wallpaper didn't change | Shortcuts → Automation → check it's set to **Run Immediately**. Run the shortcut by hand to see any error. |
| Something's missing | It might only be in a syllabus. See "Syllabus dates" in the README. |
