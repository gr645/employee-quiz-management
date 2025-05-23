# 🧠 Quiz Management System

A web-based quiz management system 💻 built with Flask and MongoDB, enabling admins to create and schedule quizzes and users to take them with real-time feedback. Designed for departments like IT, HR, Finance, and more!

## ✨ Features
### 👨‍💼 For Admins
- 🔐 Secure login
- 📤 Upload quizzes via Excel (.xlsx/.xls)
- 📅 Schedule quizzes (start time, end time)
- ⏱ Set time per question & total quiz duration
- 📊 View analytics (total submissions, average scores)
- 🏢 Department-wise performance breakdown

### 👩‍🎓 For Users
- 📝 Register & log in
- 🎯 Take quizzes specific to your department
- ⏳ Countdown timer for each question
- 📈 Progress tracking during the quiz
- 🧾 Get results instantly after submission
- 👀 One-time answer review with feedback

## 🧰 Tech Stack
- **Frontend**: HTML, CSS, JavaScript 🌐
- **Backend**: Flask (Python) 🐍
- **Database**: MongoDB 🍃
- **Libraries**: 
  - `pandas` for Excel processing 📊
  - `Chart.js` for score visualization 📈
    
📌 Notes
🗂 Excel must include columns: question, option1, option2, option3, option4, answer

🚦 One attempt per user

🔍 Answers are viewable only once — use wisely!
