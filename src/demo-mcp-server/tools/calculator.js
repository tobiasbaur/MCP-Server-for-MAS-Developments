export{ calculator }

//The actual tool function
async function calculator(args){
    const a = Number(args.a);
    const b = Number(args.b);

     let result = 0;
     switch(args.operation){
     case "add":
        result = Number(a) + Number(b);
        break;
      case "subtract":
        result = Number(a) - Number(b);
        break;
      case "multiply":
        result = Number(a) * Number(b);
        break;
      case "divide":
        if (b === 0) throw new Error("Division by zero");
        result = Number(a) / Number(b);
        break;
    }

    return {
      content: [{ type: "text", text: `${result}` }],
    };
}