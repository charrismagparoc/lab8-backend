# Connecting Web & Mobile to Django Backend

## Web App (React/Vite)

In your `src/hooks/useLocalData.js`, the `API_URL` is already set.
Change it to your backend server:

```js

const API_URL = 'http://localhost:8000/api'
```

The web `useLocalData.js` should call the Django REST API instead of Supabase.
All endpoints match: `/api/residents/`, `/api/incidents/`, etc.

## Mobile App (Expo)

In `src/hooks/useDB.js`, change:
```js
const API_URL = 'http://localhost:8000/api';
```

For Android emulator use: `http://10.0.2.2:8000/api`
For physical device use: `http://<your-computer-ip>:8000/api`

## Important Notes

- **Residents**: Mobile can POST (add), Web can only GET/PATCH (view/edit)
- **All data persists** in SQLite database (`db.sqlite3`)
- Data survives server restarts — only deleted if you manually delete or run migrations
- The `db.sqlite3` file is the persistent database

