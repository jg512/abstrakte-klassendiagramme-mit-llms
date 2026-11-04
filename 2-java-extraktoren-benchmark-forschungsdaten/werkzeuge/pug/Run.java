import de.elnarion.util.plantuml.generator.classdiagram.PlantUMLClassDiagramGenerator;
import de.elnarion.util.plantuml.generator.classdiagram.config.*;
import java.io.File;
import java.net.*;
import java.util.*;

/** args: <binDir> <jarsColonSeparated|-> <pkg...> */
public class Run {
  public static void main(String[] a) throws Exception {
    List<URL> urls = new ArrayList<>();
    urls.add(new File(a[0]).toURI().toURL());
    if (!"-".equals(a[1]))
      for (String j : a[1].split(":")) if (!j.isEmpty()) urls.add(new File(j).toURI().toURL());
    List<String> pkgs = Arrays.asList(Arrays.copyOfRange(a, 2, a.length));
    URLClassLoader cl = new URLClassLoader(urls.toArray(new URL[0]), Run.class.getClassLoader());
    PlantUMLClassDiagramConfig cfg = new PlantUMLClassDiagramConfigBuilder(pkgs)
        .withClassLoader(cl).withUseShortClassNames(true).build();
    System.out.println(new PlantUMLClassDiagramGenerator(cfg).generateDiagramText());
  }
}
