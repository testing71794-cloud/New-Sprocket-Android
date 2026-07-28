# Settings / settings — 51 Excel-generated flows



## Coverage vs screenshots (Create hub → More → Hamburger → destinations)



| Screenshot | Covered by |

|------------|------------|

| Create hub (Log in header, feature cards, More tab) | `reach_create_hub.yaml`, `assert_gallery_home.yaml` |

| Hamburger logged out (Log In, Settings, Support) | SE_01, SE_02, `assert_hamburger_menu_logged_out.yaml` |

| App Settings (Permissions, toggles, v3.0.202) | SE_07, SE_37–SE_43 |

| Printer Help sub-screens | SE_09, SE_53–SE_57 |

| Order Photo Paper / Support / Legal | SE_10–SE_12, SE_45–SE_51 |

| Log In → login options | SE_04 (`reach_login_from_hamburger.yaml` + LO_01 assertions) |

| Account Settings hidden when logged out | SE_03 |

| Logged-in Hamburger + Account Settings | SE_05–SE_35 (email login via `reach_logged_in_create_hub.yaml`) |



**Skipped duplicates:** SE_33 = SE_08, SE_36 = SE_07, SE_44 = SE_12.  

**Manual-only:** SE_25 (would change live account password).  

**Device note:** SE_30/SE_31 — Delete Account not visible on v3.0.202 email account (may need scroll/build variant).



### Logged-in subflows (new)



- `complete_email_login_valid.yaml` — credentials from LO_06

- `reach_logged_in_create_hub.yaml` — cold launch + email login

- `login_from_hamburger_email_valid.yaml` — More → Log In → email login

- `reach_module_screen_logged_in.yaml` / `assert_hamburger_menu_logged_in.yaml`

- `reach_account_settings_screen.yaml` / `assert_account_settings_screen.yaml`

- `reach_change_password_screen.yaml` + validation submit subflows

- `trigger_logout_popup.yaml` / `cancel_logout_popup.yaml` / `confirm_logout.yaml`



- [x] SE_01 | Hamburger Menu 01 | Access Hamburger Menu

- [x] SE_02 | Hamburger Menu  02 | Verify Logged Out Hamburger Menu UI

- [x] SE_03 | Hamburger Menu  03 | Verify Logged Out State

- [x] SE_04 | Hamburger Menu  04 | Verify Log In Redirection

- [x] SE_05 | Hamburger Menu  05 | Verify Logged In Hamburger Menu UI

- [x] SE_06 | Hamburger Menu  06 | Verify Close Menu Functionality

- [x] SE_07 | Hamburger Menu  07 | Verify App Settings Access

- [x] SE_08 | Hamburger Menu  08 | Verify Account Settings Access

- [x] SE_09 | Hamburger Menu  09 | Verify Printer Help

- [x] SE_10 | Hamburger Menu  10 | Verify Order Photo Paper

- [x] SE_11 | Hamburger Menu  11 | Verify Visit Support Website

- [x] SE_12 | Hamburger Menu  12 | Verify Legal & Privacy Access

- [x] SE_13 | Hamburger Menu  13 | Verify Scroll Behavior

- [x] SE_14 | Hamburger Menu  14 | Verify Header and Logo

- [x] SE_15 | Hamburger Menu 15 | Verify Log In & Navigate to Account Settings

- [x] SE_16 | Hamburger Menu 16 | Verify Name Field Display

- [x] SE_17 | Hamburger Menu 17 | Verify Change Password with Invalid Data

- [x] SE_18 | Hamburger Menu 19 | Verify Change Password Screen UI

- [x] SE_19 | Humburger Menu 20 | Verify Current Password Field

- [x] SE_20 | Hamburger Menu 21 | Verify Incorrect Current Password Error

- [x] SE_21 | Hamburger Menu 22 | Verify New Password Requirement Error

- [x] SE_22 | Hamburger Menu 23 | Verify Password Mismatch Error

- [x] SE_23 | Hamburger Menu 24 | Verify Empty Fields Validation

- [x] SE_24 | Hamburger Menu 25 | Verify Password Update Failure

- [ ] SE_25 | Hamburger Menu 26 | Verify Successful Password Change *(manual-only)*

- [x] SE_26 | Hamburger Menu 27 | Verify Back Button

- [x] SE_27 | Hamburger Menu 28 | Trigger Logout Pop-up

- [x] SE_28 | Hamburger Menu 29 | Cancel Logout

- [x] SE_29 | Hamburger Menu 30 | Confirm Logout

- [ ] SE_30 | Hamburger Menu 31 | Trigger Delete Account Pop-up *(Delete Account not on device)*

- [ ] SE_31 | Hamburger Menu 32 | Cancel Account Deletion *(depends on SE_30)*

- [x] SE_32 | Hamburger Menu 36 | Launch & Social Login *(email login path)*

- [x] SE_33 | Hamburger Menu 37 | Access Account Settings *(duplicate of SE_08)*

- [x] SE_34 | Hamburger Menu 38 | API Auth UI Validation

- [x] SE_35 | Hamburger Menu  40 | Field Constraint Validation *(email-auth variant)*

- [x] SE_36 | Hamburger Menu 41 | Navigation to App Settings *(duplicate of SE_07)*

- [x] SE_37 | Hamburger Menu 42 | Verify Permissions Option

- [x] SE_38 | Hamburger Menu 43 | Verify Default State of Display App Hints

- [x] SE_39 | Hamburger Menu 44 | Toggle App Hints ON/OFF

- [x] SE_40 | Hamburger Menu 45 | Verify Default Low Data Mode State

- [x] SE_41 | Hamburger Menu 46 | Toggle Low Data Mode Functionality

- [x] SE_42 | Hamburger Menu 47 | Verify App Version Display

- [x] SE_43 | Hamburger Menu 48 | Verify Back Navigation

- [x] SE_44 | Hamburger Menu 49 | Access Legal & Privacy Screen *(duplicate of SE_12)*

- [x] SE_45 | Hamburger Menu 50 | Data Collection Settings Navigation

- [x] SE_46 | Hamburger Menu 51 | Data Collection Exit Pop-up Validation

- [x] SE_47 | Hamburger Menu 52 | Verify Privacy Policy Open

- [x] SE_48 | Hamburger Menu 53 | Verify End User License Agreement

- [x] SE_49 | Hamburger Menu 54 | Verify Terms of Service

- [x] SE_50 | Hamburger Menu 55 | Open Source Licenses Navigation

- [x] SE_51 | Hamburger Menu 56 | Back Button Functionality



## Printer Help sub-screens (SE_53–SE_57)



- [x] SE_53 | Printer Help screen 2 | User Guide (sprocketprinters.com)

- [x] SE_54 | Printer Help screen 3 | Printer Setup (Charge + Power On)

- [x] SE_55 | Printer Help screen 4 | What Paper Size?

- [x] SE_56 | Printer Help screen 5 | Tips & Tricks

- [x] SE_57 | Printer Help screen 6 | Reset Sprocket Select

