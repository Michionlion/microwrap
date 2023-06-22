public class Version {
    public static void main(String[] args) {
        var VERSION = "1.0.0";
        if (String.join(" ", args).contains("--include-build")) {
            VERSION += "-b4";
        }
        System.out.println(VERSION);
    }
}
