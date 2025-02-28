import admin from "firebase-admin";

if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert(JSON.parse(process.env.NEXT_PUBLIC_FIREBASE_KEY)),
    projectId: "unrivaledalgo", // Ensure Admin SDK connects to `unrivaledalgo`
    databaseURL: "https://firestore.googleapis.com/v1/projects/unrivaledalgo/databases/(default)/documents"
  });
}

const adminDB = admin.firestore();

export { adminDB };
