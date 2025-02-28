// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyD1w5XmLkUw4rOAm8rXxBrIz47FVUguFmE",
  authDomain: "unrivaledalgo.firebaseapp.com",
  projectId: "unrivaledalgo",
  storageBucket: "unrivaledalgo.firebasestorage.app",
  messagingSenderId: "970585648703",
  appId: "1:970585648703:web:f7d5ff3c8f3dbc3617d28a",
  measurementId: "G-ZBN063J9TQ"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);