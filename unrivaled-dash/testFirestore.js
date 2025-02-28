import { db } from "./src/app/firebase.js";
import { collection, getDocs, query, where } from "firebase/firestore";

const testFirestore = async () => {
  try {
    console.log("🔥 Firestore DB Instance:", db);

    // Log collection path
    const collectionPath = "prop_lines";
    console.log("📁 Fetching Collection Path:", collectionPath);

    // Get collection reference
    const propLinesCollection = collection(db, collectionPath);
    console.log("📌 Collection Reference:", propLinesCollection);

    // Run query & log request arguments
    console.log("🔎 Running Firestore Query...");
    const snapshot = await getDocs(propLinesCollection);
    
    console.log("✅ Firestore Query Successful!");
    console.log("📄 Firestore Documents Retrieved:", snapshot.docs.map(doc => doc.data()));

    // Log each document with its ID
    snapshot.docs.forEach((doc) => {
      console.log(`📌 Document ID: ${doc.id}`, doc.data());
    });

  } catch (error) {
    console.error("❌ Firestore Test Error:", error);
    
    // Log Firestore-specific error details
    if (error.code) {
      console.error("🔥 Firestore Error Code:", error.code);
      console.error("⚠ Firestore Error Message:", error.message);
    }
  }
};

testFirestore();
