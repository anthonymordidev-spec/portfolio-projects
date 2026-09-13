// ===============================
// CONNECT 4
// PART 1
// ===============================

const ROWS = 6;
const COLS = 7;

let board = [];
let currentPlayer = 1;
let gameOver = false;

const boardElement = document.getElementById("board");
const turnDisplay = document.getElementById("turnDisplay");
const winnerMessage = document.getElementById("winnerMessage");
const restartBtn = document.getElementById("restartBtn");

// ===============================
// CREATE BOARD
// ===============================

function createBoard() {
  board = [];

  boardElement.innerHTML = "";

  for (let row = 0; row < ROWS; row++) {
    board[row] = [];

    for (let col = 0; col < COLS; col++) {
      board[row][col] = 0;

      const cell = document.createElement("div");

      cell.classList.add("cell");

      cell.dataset.row = row;
      cell.dataset.col = col;

      cell.addEventListener("click", () => dropPiece(col));

      boardElement.appendChild(cell);
    }
  }
}

createBoard();

// ===============================
// DROP PIECE
// ===============================

function dropPiece(col) {
  if (gameOver) return;

  for (let row = ROWS - 1; row >= 0; row--) {
    if (board[row][col] === 0) {
      board[row][col] = currentPlayer;

      placePiece(row, col);

      // CHECK FOR WIN
      if (checkWin(row, col)) {
        gameOver = true;

        winnerMessage.textContent = `🎉 Player ${currentPlayer} Wins!`;

        return;
      }

      // CHECK FOR DRAW
      if (isBoardFull()) {
        gameOver = true;

        winnerMessage.textContent = "It's a Draw!";

        return;
      }

      currentPlayer = currentPlayer === 1 ? 2 : 1;

      turnDisplay.textContent = `Player ${currentPlayer}'s Turn`;

      return;
    }
  }
}

// ===============================
// PLACE PIECE
// ===============================

function placePiece(row, col) {
  const index = row * COLS + col;

  const cell = boardElement.children[index];

  const piece = document.createElement("div");

  piece.classList.add("piece");

  if (currentPlayer === 1) {
    piece.classList.add("red");
  } else {
    piece.classList.add("yellow");
  }

  // Falling animation

  piece.style.transform = "translateY(-600px)";
  piece.style.transition = "transform .45s ease-in";

  cell.appendChild(piece);

  requestAnimationFrame(() => {
    piece.style.transform = "translateY(0)";
  });
}
// ===============================
// CHECK WIN
// ===============================

function checkWin(row, col) {
  return (
    countDirection(row, col, 0, 1) + countDirection(row, col, 0, -1) > 2 ||
    countDirection(row, col, 1, 0) + countDirection(row, col, -1, 0) > 2 ||
    countDirection(row, col, 1, 1) + countDirection(row, col, -1, -1) > 2 ||
    countDirection(row, col, 1, -1) + countDirection(row, col, -1, 1) > 2
  );
}
// ===============================
// COUNT SAME COLORED PIECES
// ===============================

function countDirection(row, col, rowDir, colDir) {
  let count = 0;

  let r = row + rowDir;

  let c = col + colDir;

  while (
    r >= 0 &&
    r < ROWS &&
    c >= 0 &&
    c < COLS &&
    board[r][c] === currentPlayer
  ) {
    count++;

    r += rowDir;

    c += colDir;
  }

  return count;
}
// ===============================
// DRAW
// ===============================

function isBoardFull() {
  for (let row = 0; row < ROWS; row++) {
    for (let col = 0; col < COLS; col++) {
      if (board[row][col] === 0) {
        return false;
      }
    }
  }

  return true;
}

// ===============================
// RESTART
// ===============================

restartBtn.addEventListener("click", () => {
  currentPlayer = 1;

  gameOver = false;

  winnerMessage.textContent = "";

  turnDisplay.textContent = "Player 1's Turn";

  createBoard();
});
