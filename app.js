const express = require("express");
const handlebars = require("express-handlebars");
const mongodbConnection = require("./configs/mongodb-conn");
const {
  addWordtoCollection,
  addWordtoUser,
} = require("./services/addWord-service");

const app = express();
app.engine(
  "handlebars",
  handlebars.engine({ helpers: require("./configs/handlebars-helpers") })
); // 템플릿 엔진으로 핸들바 등록, "handlebars"는 파일 확장자로 사용할 이름
app.set("view engine", "handlebars"); // 웹페이지 로드 시 사용할 템플릿 엔진 설정
app.set("views", __dirname + "/views"); // views 디렉터리를 views로 설정
app.use(express.json()); // req.body 해석 위한 설정
app.use(express.urlencoded({ extended: true }));

app.get("/", async (req, res) => {
  res.render("home");
});

app.get("/add", async (req, res) => {
  res.render("add");
});

app.post("/add", async (req, res) => {
  const addedWord = req.body;
  console.log(addedWord);
  const wordId = await addWordtoCollection(wordCollection, addedWord);
  const result = await addWordtoUser(userCollection, wordId);
  res.redirect("/add");
});

app.get("/learn", async(req, res));

let userCollection; // api에서 사용할 수 있게 외부에 선언
let wordCollection;
app.listen(3000, async () => {
  const mongoClient = await mongodbConnection();
  const database = mongoClient.db("chinese-voca");
  userCollection = database.collection("user");
  wordCollection = database.collection("word");
  console.log("DB connected");

  found = await userCollection.findOne({ username: "sangha" });
  console.log(found.likedWords);
});
